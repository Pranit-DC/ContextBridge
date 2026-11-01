"""Native launcher for the local product. Docker remains explicit; never publish a server."""

import argparse
import json
import secrets
import sys
import threading
import webbrowser
from contextlib import ExitStack
from pathlib import Path

import httpx
import uvicorn

from contextbridge.local_ui.settings import SettingsError, SettingsStore
from contextbridge.product.app import create_product_app
from contextbridge.product.services import Services
from contextbridge.product.settings import ProductSettings


def prepare(root):
    if not (root / "compose.yaml").is_file():
        raise SettingsError("Run from a ContextBridge release/source directory, or supply --root.")
    env = root / ".env"
    if not env.exists():
        database_password, token = secrets.token_hex(24), secrets.token_hex(32)
        values = (
            f"CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://contextbridge:{database_password}@127.0.0.1:5433/contextbridge'\n"
            f"CONTEXTBRIDGE_DB_PASSWORD='{database_password}'\nCONTEXTBRIDGE_API_TOKEN='{token}'\n"
        )
        SettingsStore(env).replace(values)
    store = SettingsStore(env)
    _, _, values = store.read()
    adapter = root / ".env.mcp"
    if not adapter.exists():
        token = values.get("CONTEXTBRIDGE_API_TOKEN", "")
        if len(token) < 32 or any(c in token for c in "'\r\n"):
            raise SettingsError("Local service access token needs review.")
        SettingsStore(adapter).replace(
            f"CONTEXTBRIDGE_API_TOKEN='{token}'\nCONTEXTBRIDGE_PROJECT_ID='contextbridge'\n"
        )
    return store


def existing(root, action):
    path = root / ".contextbridge" / "product-manager.json"
    try:
        if path.is_symlink() or path.stat().st_size > 4096:
            return None
        data = json.loads(path.read_text())
        port, token = data["port"], data["operator"]
        if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(token, str):
            return None
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=3) as client:
            response = client.post(
                f"http://127.0.0.1:{port}/api/local/v1/operator",
                headers={"X-Local-Operator": token},
                json={"action": action},
            )
        if response.status_code != 200:
            raise SettingsError(
                "The running manager could not complete this operation. Retry there."
            )
        return response.json()
    except httpx.ConnectError:
        return None  # A stale manager file after an exited process.
    except httpx.HTTPError:
        raise SettingsError(
            "The running manager is busy or unavailable. Retry before restarting."
        ) from None
    except (OSError, ValueError, KeyError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged port.")
    root = args.root.resolve()
    stack = ExitStack()
    try:
        state = root / ".contextbridge"
        if state.is_symlink():
            raise SettingsError("Unsafe local state directory.")
        if args.action == "start":
            previous = existing(root, "open")
            if previous:
                if args.no_browser:
                    print(previous["url"])
                else:
                    webbrowser.open(previous["url"])
                return 0
        elif previous := existing(root, args.action):
            print(json.dumps(previous, indent=2))
            return 0
        if args.action == "start":
            state.mkdir(mode=0o700, exist_ok=True)
            manager_lock = SettingsStore(root / ".env")
            manager_lock.state = state / "manager-lock"
            # Hold a separate installation lock for the manager lifetime.
            lock_context = manager_lock.lock()
            stack.enter_context(lock_context)
            if not (Path(__file__).parent / "web" / "index.html").is_file():
                raise SettingsError("Install a built release or build frontend assets first.")
            prepare(root)
        settings = ProductSettings(root / ".env")
        services = Services(settings, root)
        if args.action == "status":
            print(json.dumps(services.status(), indent=2))
            return 0
        if args.action == "stop":
            services.stop()
            print("Local services stopped; memory volumes retained.")
            return 0
        operator_key = secrets.token_urlsafe(32)
        app = create_product_app(
            root, port=args.port, settings=settings, services=services, operator_key=operator_key
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning"
            )
        )

        def open_browser():
            import time

            for _ in range(100):
                if server.started:
                    webbrowser.open(app.state.launch_url)
                    return
                if server.should_exit:
                    return
                time.sleep(0.1)

        if args.no_browser:
            print(app.state.launch_url)
        else:
            threading.Thread(target=open_browser, daemon=True).start()
            print(
                f"Opening ContextBridge at http://127.0.0.1:{args.port}. "
                "Keep this launcher running."
            )
        app.state.shutdown = lambda: setattr(server, "should_exit", True)
        manager_file = state / "product-manager.json"
        SettingsStore(manager_file).replace(
            json.dumps({"port": args.port, "operator": operator_key})
        )
        try:
            server.run()
        finally:
            manager_file.unlink(missing_ok=True)
        return 0
    except (SettingsError, OSError):
        print(
            "Workspace unavailable. Check the installation, secure storage and Docker.",
            file=sys.stderr,
        )
        return 1
    finally:
        stack.close()


if __name__ == "__main__":
    raise SystemExit(main())
