#!/usr/bin/env bash
# Verify the built distributions carry the right UI payloads:
# - sdist: prebuilt `web/` bundle AND editable `ui-src/` frontend sources.
# - wheel: prebuilt `web/` bundle only (runtime-only, no `ui_src/`).
# - neither: the removed `web_full` UI.
set -euo pipefail

package="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dist="$package/dist"

mapfile -t sdists < <(ls "$dist"/*.tar.gz 2>/dev/null || true)
mapfile -t wheels < <(ls "$dist"/*.whl 2>/dev/null || true)
test "${#sdists[@]}" -eq 1 || { echo "expected 1 sdist, found ${#sdists[@]}" >&2; exit 1; }
test "${#wheels[@]}" -eq 1 || { echo "expected 1 wheel, found ${#wheels[@]}" >&2; exit 1; }

python3 - "${sdists[0]}" "${wheels[0]}" <<'EOF'
import sys
import tarfile
import zipfile

sdist_path, wheel_path = sys.argv[1], sys.argv[2]

with tarfile.open(sdist_path) as tar:
    names = tar.getnames()
    assert any(n.endswith("/src/agent_chat_minimal/web/index.html") for n in names), "sdist is missing the bundled UI"
    assert not any("/web_full/" in n for n in names), "sdist must not bundle the removed web_full UI"
    for required in (
        "/ui-src/frontend/package.json",
        "/ui-src/frontend/app/page.tsx",
        "/ui-src/frontend/components/assistant-ui/thread-starter.tsx",
    ):
        assert any(n.endswith(required) for n in names), f"sdist is missing editable UI source {required}"
    for banned in (
        "/ui-src/frontend/node_modules/",
        "/ui-src/frontend/.next/",
        "/ui-src/frontend/out/",
    ):
        assert not any(banned in n for n in names), f"sdist must not bundle install/build output {banned}"

with zipfile.ZipFile(wheel_path) as whl:
    names = whl.namelist()
    assert "agent_chat_minimal/web/index.html" in names, "wheel is missing the bundled UI"
    assert not any(n.startswith("agent_chat_minimal/web_full/") for n in names), "wheel must not bundle the removed web_full UI"
    assert not any(n.startswith("agent_chat_minimal/ui_src/") for n in names), "wheel must stay runtime-only (no ui_src/)"

print(f"distributions verified: {sdist_path} + {wheel_path}")
EOF
