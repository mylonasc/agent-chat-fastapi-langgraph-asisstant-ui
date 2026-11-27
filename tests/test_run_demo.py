"""Offline CLI regression tests: no Docker daemon or model credentials needed.

Run from the checkout: python -m unittest discover -s tests -p test_run_demo.py
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_demo"


class RunDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-demo-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout with spaces"
        (self.root / "scripts").mkdir(parents=True)
        self.script = self.root / "scripts" / "run_demo"
        shutil.copy2(SCRIPT, self.script)
        self.env_file = self.root / ".env"
        self.env_file.write_text("OPENAI_API_KEY=example\n")
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.temp.name) / "docker-calls.jsonl"
        docker = self.bin / "docker"
        docker.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['RUN_DEMO_TEST_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "if args == ['compose', 'version']:\n"
            "    sys.exit(int(os.environ.get('TEST_COMPOSE_STATUS', '0')))\n"
            "if args == ['info']:\n"
            "    sys.exit(int(os.environ.get('TEST_DOCKER_STATUS', '0')))\n"
            "sys.exit(int(os.environ.get('TEST_ACTION_STATUS', '0')))\n"
        )
        docker.chmod(0o755)
        for tool in ("uv", "node", "pnpm"):
            shutil.copy2(docker, self.bin / tool)
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "RUN_DEMO_TEST_LOG": str(self.log),
        }

    def run_demo(self, *args, **env):
        # Deliberately run outside the checkout to check path resolution.
        return subprocess.run(
            [str(self.script), *args],
            cwd=self.temp.name,
            env={**self.env, **env},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def compose_command(self, setup, *args):
        return [
            "compose",
            "--project-directory",
            str(self.root),
            "--env-file",
            str(self.env_file),
            "--file",
            str(self.root / f"docker-compose.{setup}.yml"),
            *args,
        ]

    def test_default_rebuilds_minimal_from_any_directory(self):
        result = self.run_demo()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls()[-1], self.compose_command("minimal", "up", "--build")
        )
        self.assertIn("http://localhost:3000", result.stdout)
        self.assertIn("http://localhost:8011/docs", result.stdout)

    def test_full_detached_waits_for_services(self):
        result = self.run_demo("--full", "--detach")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls()[-1],
            self.compose_command(
                "full",
                "up",
                "--build",
                "--detach",
                "--wait",
                "--wait-timeout",
                "180",
            ),
        )
        self.assertIn("http://localhost:3001", result.stdout)
        self.assertIn("http://localhost:8010/docs", result.stdout)

    def test_short_flags(self):
        result = self.run_demo("-m", "-d")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--detach", self.calls()[-1])

    def test_no_build_is_explicit(self):
        result = self.run_demo("--full", "--no-build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls()[-1], self.compose_command("full", "up", "--no-build")
        )
        self.assertIn("not rebuilt", result.stdout)

    def test_stop_does_not_remove_volumes_or_other_setup(self):
        result = self.run_demo("--full", "--stop")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1], self.compose_command("full", "down"))

    def test_logs_do_not_start_or_build(self):
        result = self.run_demo("--minimal", "--logs")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls()[-1],
            self.compose_command(
                "minimal",
                "logs",
                "--follow",
                "--tail",
                "100",
            ),
        )

    def test_help_needs_no_configuration_or_docker(self):
        self.env_file.unlink()
        result = self.run_demo("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage:", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_dry_run_does_not_run_docker_or_create_env(self):
        self.env_file.unlink()
        result = self.run_demo("--full", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docker-compose.full.yml", result.stdout)
        self.assertIn("up --build", result.stdout)
        self.assertFalse(self.env_file.exists())
        self.assertEqual(self.calls(), [])

    def test_invalid_arguments_do_not_touch_docker(self):
        for args in [
            ("--minimal", "--full"),
            ("--logs", "--stop"),
            ("--stop", "--detach"),
            ("--logs", "--no-build"),
            ("--unknown",),
        ]:
            with self.subTest(args=args):
                result = self.run_demo(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("run_demo:", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_missing_env_has_setup_instructions(self):
        self.env_file.unlink()
        result = self.run_demo("--full")
        self.assertEqual(result.returncode, 2)
        self.assertIn(".env.example", result.stderr)
        self.assertIn("OPENAI_API_KEY", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_env_is_not_executed_or_overwritten(self):
        sentinel = self.root / "must-not-exist"
        content = f'OPENAI_API_KEY=$(touch "{sentinel}")\n'
        self.env_file.write_text(content)
        result = self.run_demo("--full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(sentinel.exists())
        self.assertEqual(self.env_file.read_text(), content)
        self.assertNotIn(content.strip(), result.stdout + result.stderr)

    def test_missing_compose_is_actionable(self):
        result = self.run_demo(TEST_COMPOSE_STATUS="1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Compose v2", result.stderr)
        self.assertEqual(self.calls(), [["compose", "version"]])

    def test_unavailable_docker_is_actionable(self):
        result = self.run_demo(TEST_DOCKER_STATUS="1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Start Docker", result.stderr)
        self.assertEqual(self.calls(), [["compose", "version"], ["info"]])

    def test_compose_failure_is_not_reported_as_success(self):
        result = self.run_demo("--full", "--detach", TEST_ACTION_STATUS="17")
        self.assertEqual(result.returncode, 17)
        self.assertNotIn("http://localhost:3001", result.stdout)

    def test_local_minimal_uses_canonical_package_without_docker(self):
        result = self.run_demo("--local", "--minimal")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        command = calls[0]
        self.assertEqual(
            command[:3],
            ["run", "--project", str(self.root / "packages/agent-chat-minimal")],
        )
        self.assertIn("--frozen", command)
        self.assertIn("persistence", command)
        self.assertIn(str(self.env_file), command)
        self.assertIn(str(self.root / "scripts/run_demo_local.py"), command)
        self.assertEqual(command[-4:], ["--ui-port", "3000", "--api-port", "8011"])

    def test_local_full_can_override_ports_and_skip_dependency_install(self):
        result = self.run_demo(
            "--local", "--full", "--no-build", "--ui-port", "3101", "--api-port", "8110"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        command = self.calls()[0]
        self.assertIn(str(self.root / "packages/agent-chat-minimal"), command)
        self.assertIn("--no-sync", command)
        self.assertNotIn("--frozen", command)
        self.assertEqual(
            command[-5:], ["--ui-port", "3101", "--api-port", "8110", "--skip-install"]
        )

    def test_local_dry_run_requires_no_tools_or_env(self):
        self.env_file.unlink()
        result = self.run_demo("--full", "--local", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uv run", result.stdout)
        self.assertIn("run_demo_local.py", result.stdout)
        self.assertNotIn("docker compose", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_consistent_runtime_ui_and_toolset_flags(self):
        result = self.run_demo(
            "--runtime",
            "local",
            "--ui",
            "full",
            "--toolsets",
            "calculator,weather",
            "--allow-toolsets",
            "calculator,weather,graph",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        command = self.calls()[0]
        self.assertEqual(
            command[-4:],
            [
                "--toolsets",
                "calculator,weather",
                "--allow-toolsets",
                "calculator,weather,graph",
            ],
        )
        self.assertIn("full", command)

    def test_docker_forwards_the_same_toolsets_to_compose(self):
        result = self.run_demo(
            "--runtime", "docker", "--ui", "full", "--toolsets", "calculator"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docker-compose.full.yml", " ".join(self.calls()[-1]))

    def test_invalid_local_options_and_ports_are_rejected(self):
        for args in [
            ("--local", "--detach"),
            ("--local", "--stop"),
            ("--local", "--logs"),
            ("--ui-port", "3100"),
            ("--local", "--api-port"),
            ("--local", "--api-port", "0"),
            ("--local", "--api-port", "65536"),
            ("--local", "--api-port", "oops"),
            ("--local", "--api-port", "3100", "--ui-port", "3100"),
        ]:
            with self.subTest(args=args):
                result = self.run_demo(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
