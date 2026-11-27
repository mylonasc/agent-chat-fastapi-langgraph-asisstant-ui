"""Build an isolated wheel with the latest static export, then smoke it offline.

Run `pnpm --dir application/frontend/frontend build` first, then:
python3 tests/ui/scripts/check-toolsets-wheel.py
No tracked files, original staged assets, model APIs, or existing databases change.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def smoke():
    import agent_chat_minimal
    from agent_chat_minimal import Settings
    from agent_chat_minimal.composition import create_configured_app
    from fastapi.testclient import TestClient

    assert "site-packages" in str(agent_chat_minimal.__file__), (
        agent_chat_minimal.__file__
    )
    help_result = subprocess.run(
        ["agent-chat-serve", "--help"], capture_output=True, text=True, check=True
    )
    assert "--toolsets" in help_result.stdout and "--ui" in help_result.stdout
    assert importlib.util.find_spec("faiss") is None
    assert importlib.util.find_spec("fastembed") is None
    os.environ["AGENT_CHAT_ADMIN_TOKEN"] = "wheel-smoke-token"
    with tempfile.TemporaryDirectory(prefix="toolsets-wheel-state-") as folder:
        root = Path(folder)
        settings = Settings(
            ui_preset="full",
            toolsets=("calculator", "weather"),
            persistence_enabled=True,
            tool_settings_path=str(root / "tools.sqlite3"),
            database_path=str(root / "chat.sqlite3"),
            checkpoint_database_path=str(root / "checkpoints.sqlite3"),
        )
        headers = {"x-agent-chat-subject": "wheel-owner"}
        with TestClient(create_configured_app(settings)) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/api/config").json()["tooling"]["enabled"]
            page = client.get("/toolsets/")
            assert page.status_code == 200 and "Toolsets and tools" in page.text
            assert client.get("/tooling/admin").status_code == 403
            assert (
                client.post(
                    "/threads", headers=headers, json={"localId": "wheel-thread"}
                ).status_code
                == 200
            )
            snapshot = client.get("/threads/wheel-thread/tools", headers=headers).json()
            update = {
                "revision": snapshot["revision"],
                "global_revision": snapshot["global_revision"],
                "toolsets": ["calculator"],
                "tools": {"divide": {"config": {"precision": 2}}},
            }
            assert (
                client.put(
                    "/threads/wheel-thread/tools", headers=headers, json=update
                ).status_code
                == 200
            )
        with TestClient(create_configured_app(settings)) as client:
            snapshot = client.get("/threads/wheel-thread/tools", headers=headers).json()
            assert snapshot["enabled_tools"]["divide"]["precision"] == 2
            assert "get_weather" not in snapshot["enabled_tools"]
    print(
        json.dumps(
            {
                "artifact": "wheel",
                "ui": "full",
                "tools_ui": "served",
                "runtime_settings": "durable",
                "heavy_rag_dependencies": False,
                "model_calls": 0,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    if parser.parse_args().smoke:
        smoke()
        return
    repo = Path(__file__).resolve().parents[3]
    exported = repo / "application/frontend/frontend/out"
    if not (exported / "toolsets/index.html").exists():
        raise SystemExit(
            "Build the frontend first: pnpm --dir application/frontend/frontend build"
        )
    with tempfile.TemporaryDirectory(prefix="toolsets-wheel-build-") as folder:
        root = Path(folder)
        project = root / "package"
        shutil.copytree(
            repo / "packages/agent-chat-minimal",
            project,
            ignore=shutil.ignore_patterns(
                ".venv", "dist", "web", "web_full", "ui_src", "__pycache__", ".gitkeep"
            ),
        )
        shutil.copytree(exported, project / "src/agent_chat_minimal/web")
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(root / "dist"), str(project)],
            check=True,
        )
        wheel = next((root / "dist").glob("*.whl"))
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("AGENT_CHAT_CONFIG", None)
        subprocess.run(
            [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--with",
                f"{wheel}[persistence]",
                "python",
                str(Path(__file__).resolve()),
                "--smoke",
            ],
            check=True,
            cwd=root,
            env=env,
        )


if __name__ == "__main__":
    main()
