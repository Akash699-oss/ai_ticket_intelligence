from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent


def _terminate(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _wait_for_backend(url: str, process: subprocess.Popen, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"FastAPI exited during startup with code {process.returncode}")
        try:
            response = requests.get(f"{url}/health", timeout=1.5)
            if response.ok:
                return
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.4)
    suffix = f" Last error: {last_error}" if last_error else ""
    raise RuntimeError(f"FastAPI did not become healthy within {timeout:.0f}s.{suffix}")


def main() -> None:
    env = os.environ.copy()
    api_host = env.get("API_HOST", "127.0.0.1")
    api_port = env.get("API_PORT", "8000")
    ui_host = env.get("UI_HOST", "127.0.0.1")
    ui_port = env.get("UI_PORT", "8501")

    # The UI and backend are launched on the same machine/process namespace, so
    # loopback is the safest default even when API_HOST is 0.0.0.0 for external binding.
    internal_api_url = env.get("API_URL", f"http://127.0.0.1:{api_port}")

    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            api_host,
            "--port",
            api_port,
        ],
        cwd=ROOT,
        env=env,
    )
    processes = [backend]

    try:
        _wait_for_backend(internal_api_url, backend)

        ui_env = {**env, "API_URL": internal_api_url}
        ui = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "ui.py",
                "--server.address",
                ui_host,
                "--server.port",
                ui_port,
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=ROOT,
            env=ui_env,
        )
        processes.append(ui)

        api_display_host = "127.0.0.1" if api_host == "0.0.0.0" else api_host
        ui_display_host = "127.0.0.1" if ui_host == "0.0.0.0" else ui_host
        print(f"FastAPI:  http://{api_display_host}:{api_port}")
        print(f"Swagger:  http://{api_display_host}:{api_port}/docs")
        print(f"Streamlit: http://{ui_display_host}:{ui_port}")
        print("Press Ctrl+C to stop both services.")

        while True:
            if backend.poll() is not None:
                raise RuntimeError(f"FastAPI exited with code {backend.returncode}")
            if ui.poll() is not None:
                raise RuntimeError(f"Streamlit exited with code {ui.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        _terminate(processes)


if __name__ == "__main__":
    main()
