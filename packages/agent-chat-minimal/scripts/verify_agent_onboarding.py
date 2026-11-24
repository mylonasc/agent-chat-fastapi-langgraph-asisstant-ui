"""Installed-artifact onboarding smoke check; stdlib only, no network needed.

Run with the artifact's Python interpreter. The temporary working directory
and absolute console-script paths prevent accidental reliance on a checkout.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    with tempfile.TemporaryDirectory(prefix="agent-onboarding-") as directory:
        def run(command, *args, status=0):
            result = subprocess.run(
                [str(Path(sys.executable).parent / command), *args],
                cwd=directory, env=env, capture_output=True, text=True, timeout=30,
            )
            assert result.returncode == status, (command, result.stdout, result.stderr)
            assert result.stderr == "", (command, result.stderr)
            return json.loads(result.stdout)

        description = run("minimal-chat-setup", "describe", "--json")
        guides = run("minimal-chat-docs", "list", "--json")["guides"]
        assert description["documentation"] == guides
        assert {guide["name"] for guide in guides} >= {"agent-onboarding", "setup", "starter", "ollama-quickstart"}
        assert description["commands"]["local_ollama"] == ["minimal-chat-docs", "show", "ollama-quickstart"]
        assert "ollama pull" in run("minimal-chat-docs", "show", "ollama-quickstart", "--json")["markdown"]
        assert run("minimal-chat-docs", "show", "agent-onboarding", "--json")["markdown"]
        assert run("minimal-chat-docs", "search", "persistence", "--json")["matches"]
        assert run("minimal-chat-docs", "show", "unknown", "--json", status=2)["ok"] is False
        assert run("minimal-chat-setup", "schema", "--json")["title"] == "Agent Chat configuration"
        report = run("minimal-chat-setup", "doctor", "--json", status=2)
        assert report["valid"] and not report["ready"]
        assert report["connectivity"] == "not_tested"
        assert any(item["code"] == "missing_credential" for item in report["diagnostics"])
        assert any(item["kind"] == "bundled_ui" and item["present"] for item in report["checks"])
        target = Path(directory) / "test-site"
        preview = run("minimal-chat-init", str(target), "--preset", "full", "--dry-run", "--json")
        assert not target.exists()
        generated = run("minimal-chat-init", str(target), "--preset", "full", "--json")
        assert generated["plan"] == preview["plan"]
        assert generated["next_steps"] == preview["next_steps"]
        assert (target / "AGENTS.md").is_file()
        assert run("minimal-chat-init", str(target), "--json", status=2)["code"] == "target_conflicts"
    print("installed-artifact agent onboarding passed")


if __name__ == "__main__":
    main()
