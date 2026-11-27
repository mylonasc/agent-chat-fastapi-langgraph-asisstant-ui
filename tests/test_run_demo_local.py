"""Exercise the real local supervisor with deterministic, disposable HTTP servers.

No dependency downloads, Docker daemon, or model calls are used.
Run: python -m unittest discover -s tests -p 'test_run_demo*.py'
"""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest


SUPERVISOR = Path(__file__).resolve().parents[1] / "scripts/run_demo_local.py"
FAKE_SERVER = """
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

def record(name):
    with open(os.environ["LOCAL_TEST_LOG"], "a") as log:
        log.write(json.dumps({"name": name, "pid": os.getpid(), "cwd": os.getcwd(),
            "args": sys.argv[1:], "api_base": os.environ.get("API_BASE"),
            "public_api": os.environ.get("NEXT_PUBLIC_API_BASE"),
            "preset": os.environ.get("UI_PRESET")}) + "\\n")

def serve(name):
    record(name)
    if os.environ.get("FAIL_SERVER") == name:
        sys.exit(9)
    port = int(sys.argv[sys.argv.index("--port") + 1])
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ready")
        def log_message(self, *args):
            pass
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class LocalDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="local-demo-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout with spaces"
        for folder in (
            "application/frontend/frontend",
            "application/backend/full",
            "packages/agent-chat-minimal",
        ):
            (self.root / folder).mkdir(parents=True)
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        modules = Path(self.temp.name) / "modules"
        modules.mkdir()
        (modules / "fake_server.py").write_text(FAKE_SERVER)
        (modules / "uvicorn.py").write_text(
            'from fake_server import serve\nserve("backend")\n'
        )
        package = modules / "agent_chat_minimal"
        (package / "toolkits").mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "config.py").write_text(
            "class Settings:\n    allowed_toolsets = None\n    toolsets = ('calculator',)\n    tool_settings_path = 'tool-settings.sqlite3'\n    tool_data_path = 'data/web_rag'\n    database_path = 'agent-chat.db'\n    checkpoint_database_path = 'agent-chat-checkpoints.db'\n    persistence_enabled = True\n    @staticmethod\n    def load():\n        return Settings()\n"
        )
        (package / "toolkits/__init__.py").write_text("")
        (package / "toolkits/catalog.py").write_text(
            "def installation_extras(names):\n    return ()\n"
        )
        pnpm = self.bin / "pnpm"
        pnpm.write_text(
            f"#!{sys.executable}\n"
            "import os, sys\nfrom fake_server import record, serve\n"
            "if sys.argv[1] == 'install':\n"
            "    record('install')\n"
            "    sys.exit(int(os.environ.get('FAIL_INSTALL', '0')))\n"
            "serve('frontend')\n"
        )
        pnpm.chmod(0o755)
        self.events = Path(self.temp.name) / "events.jsonl"
        self.output = Path(self.temp.name) / "output.txt"
        self.ui_port, self.api_port = free_port(), free_port()
        while self.ui_port == self.api_port:
            self.api_port = free_port()
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "PYTHONPATH": str(modules),
            "LOCAL_TEST_LOG": str(self.events),
        }

    def start(self, setup="full", skip_install=False, **env):
        command = [
            sys.executable,
            str(SUPERVISOR),
            "--root",
            str(self.root),
            "--setup",
            setup,
            "--ui-port",
            str(self.ui_port),
            "--api-port",
            str(self.api_port),
        ]
        if skip_install:
            command.append("--skip-install")
        output = self.output.open("w")
        self.addCleanup(output.close)
        process = subprocess.Popen(
            command, env={**self.env, **env}, stdout=output, stderr=output
        )
        self.addCleanup(self.stop, process)
        return process

    def stop(self, process):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=12)

    def records(self):
        return (
            [json.loads(line) for line in self.events.read_text().splitlines()]
            if self.events.exists()
            else []
        )

    def wait_ready(self, process):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if "local demo ready" in self.output.read_text():
                return
            if process.poll() is not None:
                self.fail(self.output.read_text())
            time.sleep(0.05)
        self.fail(f"Demo did not start: {self.output.read_text()}")

    def assert_ports_closed(self):
        for port in (self.ui_port, self.api_port):
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)

    def test_full_ready_env_routing_and_sigterm_cleanup(self):
        process = self.start()
        self.wait_ready(process)
        records = self.records()
        self.assertEqual(
            [item["name"] for item in records], ["install", "backend", "frontend"]
        )
        backend, frontend = records[1:]
        self.assertIn("agent_chat_minimal:create_default_app", backend["args"])
        self.assertIn("--reload", backend["args"])
        self.assertEqual(backend["cwd"], str(self.root / "packages/agent-chat-minimal"))
        self.assertEqual(frontend["public_api"], f"http://localhost:{self.api_port}")
        self.assertEqual(backend["api_base"], frontend["public_api"])
        self.assertEqual(backend["preset"], "full")
        process.terminate()
        self.assertEqual(process.wait(timeout=12), 143)
        self.assert_ports_closed()

    def test_minimal_uses_package_factory_and_sigint_cleanup(self):
        process = self.start(setup="minimal", skip_install=True)
        self.wait_ready(process)
        records = self.records()
        self.assertEqual([item["name"] for item in records], ["backend", "frontend"])
        self.assertIn("agent_chat_minimal:create_default_app", records[0]["args"])
        self.assertIn("--factory", records[0]["args"])
        self.assertEqual(records[0]["preset"], "minimal")
        process.send_signal(signal.SIGINT)
        self.assertEqual(process.wait(timeout=12), 130)
        self.assert_ports_closed()

    def test_frontend_failure_cleans_up_backend(self):
        process = self.start(FAIL_SERVER="frontend")
        self.assertEqual(process.wait(timeout=12), 1)
        self.assertIn("Frontend exited with status 9", self.output.read_text())
        self.assert_ports_closed()

    def test_backend_failure_does_not_launch_frontend(self):
        process = self.start(FAIL_SERVER="backend")
        self.assertEqual(process.wait(timeout=12), 1)
        self.assertIn("Backend exited with status 9", self.output.read_text())
        self.assertNotIn("frontend", [item["name"] for item in self.records()])
        self.assert_ports_closed()

    def test_dependency_install_failure_does_not_start_servers(self):
        process = self.start(FAIL_INSTALL="7")
        self.assertEqual(process.wait(timeout=12), 1)
        self.assertIn("pnpm install failed with status 7", self.output.read_text())
        self.assertEqual([item["name"] for item in self.records()], ["install"])

    def test_port_conflict_does_not_install_or_stop_existing_service(self):
        with socket.socket() as existing:
            existing.bind(("127.0.0.1", self.api_port))
            existing.listen()
            process = self.start()
            self.assertEqual(process.wait(timeout=12), 1)
            self.assertIn(
                f"Port {self.api_port} is unavailable", self.output.read_text()
            )
            self.assertEqual(self.records(), [])
            with socket.socket() as probe:
                self.assertEqual(probe.connect_ex(("127.0.0.1", self.api_port)), 0)


@unittest.skipUnless(
    os.environ.get("RUN_DEMO_LIVE") in {"minimal", "full"}, "Opt-in real local servers"
)
class LiveLocalDemoTests(unittest.TestCase):
    def test_real_launcher_startup_config_and_shutdown(self):
        from urllib.request import urlopen

        setup = os.environ["RUN_DEMO_LIVE"]
        ui_port, api_port = free_port(), free_port()
        while ui_port == api_port:
            api_port = free_port()
        command = [
            str(SUPERVISOR.with_name("run_demo")),
            "--local",
            f"--{setup}",
            "--ui-port",
            str(ui_port),
            "--api-port",
            str(api_port),
        ]
        if os.environ.get("RUN_DEMO_SKIP_INSTALL") == "1":
            command.append("--no-build")
        with tempfile.TemporaryFile(mode="w+") as output:
            process = subprocess.Popen(command, stdout=output, stderr=output)
            try:
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    output.seek(0)
                    log = output.read()
                    if "local demo ready" in log:
                        break
                    if process.poll() is not None:
                        self.fail(log[-5000:])
                    time.sleep(0.5)
                else:
                    self.fail(f"Startup timed out: {log[-5000:]}")
                with urlopen(
                    f"http://127.0.0.1:{api_port}/api/config", timeout=5
                ) as response:
                    config = json.load(response)
                self.assertEqual(config["ui_preset"], setup)
                self.assertEqual(
                    config["api_base"].rstrip("/"), f"http://localhost:{api_port}"
                )
                with urlopen(f"http://127.0.0.1:{ui_port}/", timeout=20) as response:
                    self.assertEqual(response.status, 200)
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                process.wait(timeout=15)
            for port in (ui_port, api_port):
                with socket.socket() as probe:
                    self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)


if __name__ == "__main__":
    unittest.main()
