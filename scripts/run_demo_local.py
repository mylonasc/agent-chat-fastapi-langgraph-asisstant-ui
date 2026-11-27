"""Foreground local-mode supervisor, invoked by run_demo inside uv's environment."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


class Interrupted(Exception):
    def __init__(self, signum):
        self.exit_code = 128 + signum


def interrupt(signum, _frame):
    raise Interrupted(signum)


def check_ports(ports):
    for port in ports:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise RuntimeError(
                    f"Port {port} is unavailable. Stop the existing demo or choose "
                    "different --ui-port / --api-port values."
                ) from exc


def check_children(children):
    for name, child in children:
        status = child.poll()
        if status is not None:
            raise RuntimeError(
                f"{name} exited with status {status}; see its output above."
            )


def wait_http(url, children, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_children(children)
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}; see server output above.")


def cleanup(children):
    # Each child owns a process group, including uvicorn reloaders / Next workers.
    # Never kill by port or by executable name: other demos must remain untouched.
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, signal.SIG_IGN)
    for _, child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        groups_alive = False
        for _, child in children:
            child.poll()
            try:
                os.killpg(child.pid, 0)
                groups_alive = True
            except ProcessLookupError:
                pass
        if not groups_alive:
            break
        time.sleep(0.1)
    for _, child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--setup", choices=("minimal", "full"), required=True)
    parser.add_argument("--ui-port", type=int, required=True)
    parser.add_argument("--api-port", type=int, required=True)
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--toolsets")
    parser.add_argument("--allow-toolsets")
    args = parser.parse_args()
    children = []

    def start(name, command, cwd, env):
        child = subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)
        children.append((name, child))
        return child

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, interrupt)
    try:
        check_ports((args.ui_port, args.api_port))
        frontend = args.root / "application/frontend/frontend"
        api_url = f"http://localhost:{args.api_port}"
        env = {
            **os.environ,
            "API_BASE": api_url,
            "UI_PRESET": args.setup,
            "PORT": str(args.api_port),
            "HOST": "127.0.0.1",
        }
        if args.toolsets is not None:
            env["TOOLSETS"] = args.toolsets
        elif not env.get("AGENT_CHAT_CONFIG"):
            env.setdefault("TOOLSETS", "calculator,weather,graph")
        if args.allow_toolsets is not None:
            env["ALLOWED_TOOLSETS"] = args.allow_toolsets
        if env.get("AGENT_CHAT_CONFIG"):
            config_path = Path(env["AGENT_CHAT_CONFIG"]).expanduser()
            env["AGENT_CHAT_CONFIG"] = str(
                config_path if config_path.is_absolute() else args.root / config_path
            )
        from agent_chat_minimal.config import Settings
        from agent_chat_minimal.toolkits.catalog import installation_extras

        previous = dict(os.environ)
        os.environ.update(env)
        try:
            resolved = Settings.load()
        finally:
            os.environ.clear()
            os.environ.update(previous)
        state_dir = args.root / ".demo-data" / args.setup
        defaults = Settings()
        for name, attribute, filename in (
            ("TOOL_SETTINGS_PATH", "tool_settings_path", "tool-settings.sqlite3"),
            ("TOOL_DATA_PATH", "tool_data_path", "web_rag"),
            ("DATABASE_PATH", "database_path", "chat.sqlite3"),
            (
                "CHECKPOINT_DATABASE_PATH",
                "checkpoint_database_path",
                "checkpoints.sqlite3",
            ),
        ):
            if (
                name.startswith(("DATABASE", "CHECKPOINT"))
                and not resolved.persistence_enabled
            ):
                continue
            if name not in env and getattr(resolved, attribute) == getattr(
                defaults, attribute
            ):
                env[name] = str(state_dir / filename)
        frontend_env = {
            **env,
            "NEXT_PUBLIC_API_BASE": api_url,
            "NEXT_PUBLIC_UI_BASE_PATH": "",
        }
        if not args.skip_install:
            # The same registry decides optional dependencies for native and
            # container builds. Read YAML/env through the canonical settings.
            extras = installation_extras(
                resolved.allowed_toolsets
                if resolved.allowed_toolsets is not None
                else (resolved.toolsets or ())
            )
            if extras:
                command = [
                    "uv",
                    "sync",
                    "--project",
                    str(args.root / "packages/agent-chat-minimal"),
                    "--python",
                    "3.11",
                    "--frozen",
                    "--no-dev",
                    "--extra",
                    "persistence",
                ]
                for extra in extras:
                    command.extend(["--extra", extra])
                sync = start("Optional Python dependencies", command, args.root, env)
                if sync.wait():
                    raise RuntimeError("Optional Python dependency installation failed")
                children.remove(("Optional Python dependencies", sync))
            print("Installing frontend dependencies from the lockfile...", flush=True)
            install = start(
                "pnpm install",
                ["pnpm", "install", "--frozen-lockfile"],
                frontend,
                frontend_env,
            )
            status = install.wait()
            if status:
                raise RuntimeError(f"pnpm install failed with status {status}.")
            children.remove(("pnpm install", install))

        backend = args.root / "packages/agent-chat-minimal"
        app = "agent_chat_minimal:create_default_app"
        backend_command = [sys.executable, "-m", "uvicorn", app]
        backend_command.append("--factory")
        backend_command.extend(
            ["--host", "127.0.0.1", "--port", str(args.api_port), "--reload"]
        )
        start("Backend", backend_command, backend, env)
        print(f"Waiting for backend on {api_url}...", flush=True)
        wait_http(f"http://127.0.0.1:{args.api_port}/health", children)
        start(
            "Frontend",
            ["pnpm", "dev", "--hostname", "127.0.0.1", "--port", str(args.ui_port)],
            frontend,
            frontend_env,
        )
        wait_http(f"http://127.0.0.1:{args.ui_port}/", children)
        print(
            f"\n{args.setup} local demo ready\n"
            f"  Chat:     http://localhost:{args.ui_port}\n"
            f"  API docs: {api_url}/docs\n"
            f"  Health:   {api_url}/health\n\n"
            "Source changes hot reload. Ctrl-C stops both servers.",
            flush=True,
        )
        while True:
            check_children(children)
            time.sleep(0.2)
    except Interrupted as exc:
        return exc.exit_code
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"run_demo: {exc}", file=sys.stderr)
        return 1
    finally:
        cleanup(children)


if __name__ == "__main__":
    sys.exit(main())
