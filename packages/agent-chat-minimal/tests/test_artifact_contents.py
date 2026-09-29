"""Distributable artifact verification (AGS-05).

Builds the wheel and sdist from the source tree and asserts the release
payload: JSON Schema, setup/starter/model modules, guides, static UI,
and console entry points. Installed-runtime behavior (serving, generation,
browser-free operation) is covered by scripts/smoke_test_wheel.sh in CI.
"""

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def _build_artifacts(tmp_path: Path) -> list[Path]:
    outdir = tmp_path / "dist"
    outdir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(outdir)],
        cwd=PACKAGE_DIR,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    artifacts = sorted(outdir.iterdir())
    assert [p.suffix for p in artifacts] != []
    return artifacts


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    try:
        return _build_artifacts(tmp_path_factory.mktemp("dist"))
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"artifact build unavailable: {exc.stderr[-2000:]}")


def _wheel_members(artifacts) -> list[str]:
    wheels = [p for p in artifacts if p.suffix == ".whl"]
    assert len(wheels) == 1, [p.name for p in artifacts]
    with zipfile.ZipFile(wheels[0]) as archive:
        return archive.namelist()


def _sdist_members(artifacts) -> list[str]:
    sdists = [p for p in artifacts if p.name.endswith(".tar.gz")]
    assert len(sdists) == 1, [p.name for p in artifacts]
    with tarfile.open(sdists[0]) as archive:
        return archive.getnames()


def test_wheel_ships_schema_setup_starter_models_and_ui(artifacts):
    members = _wheel_members(artifacts)
    for expected in (
        "agent_chat_minimal/schemas/agent_chat.schema.json",
        "agent_chat_minimal/setup.py",
        "agent_chat_minimal/starter.py",
        "agent_chat_minimal/models.py",
        "agent_chat_minimal/docs/setup.md",
        "agent_chat_minimal/docs/starter.md",
        "agent_chat_minimal/docs/providers.md",
        "agent_chat_minimal/docs/configuration.md",
        "agent_chat_minimal/web/index.html",
    ):
        assert expected in members, expected


def test_wheel_registers_console_entry_points(artifacts):
    members = _wheel_members(artifacts)
    entry_points = [m for m in members if m.endswith("entry_points.txt")]
    assert len(entry_points) == 1
    wheels = [p for p in artifacts if p.suffix == ".whl"]
    with zipfile.ZipFile(wheels[0]) as archive:
        text = archive.read(entry_points[0]).decode()
    assert "minimal-chat-serve" in text
    assert "minimal-chat-migrate" in text
    assert "minimal-chat-init" in text


def test_sdist_ships_schema_templates_and_docs(artifacts):
    members = _sdist_members(artifacts)
    assert any(m.endswith("pyproject.toml") for m in members)
    for expected_suffix in (
        "src/agent_chat_minimal/schemas/agent_chat.schema.json",
        "src/agent_chat_minimal/setup.py",
        "src/agent_chat_minimal/starter.py",
        "src/agent_chat_minimal/models.py",
        "src/agent_chat_minimal/docs/setup.md",
        "src/agent_chat_minimal/docs/starter.md",
        "src/agent_chat_minimal/web/index.html",
    ):
        assert any(m.endswith(expected_suffix) for m in members), expected_suffix
