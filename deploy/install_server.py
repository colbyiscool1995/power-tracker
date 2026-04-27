#!/usr/bin/env python3
"""Install power-tracker server (RUN_MODE=server) as a background service."""

import os
import platform
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()
PYTHON = sys.executable
SERVICE_NAME = "power-tracker-server"
ENV_FILE = REPO_DIR / ".env"


def _check_env():
    if not ENV_FILE.exists():
        print(f"ERROR: .env not found at {ENV_FILE}")
        print("Copy .env.example to .env and fill in values.")
        sys.exit(1)
    content = ENV_FILE.read_text()
    if "RUN_MODE=server" not in content:
        print("WARNING: RUN_MODE is not set to 'server' in .env")
        print("Update .env: RUN_MODE=server")


def _install_deps():
    print("Installing Python dependencies ...")
    req = REPO_DIR / "requirements.txt"
    result = subprocess.run(
        [PYTHON, "-m", "pip", "install", "-r", str(req)],
        check=False,
    )
    if result.returncode != 0:
        print("ERROR: dependency installation failed.")
        sys.exit(1)
    print("Dependencies installed.")


def _parse_env() -> dict[str, str]:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


# ── Linux ────────────────────────────────────────────────────────────────────

def _fix_selinux_context():
    result = subprocess.run(["which", "semanage"], capture_output=True)
    if result.returncode != 0:
        return
    print(f"Setting SELinux context on {ENV_FILE} ...")
    subprocess.run(
        ["sudo", "semanage", "fcontext", "-a", "-t", "etc_t", str(ENV_FILE)],
        check=False,
    )
    subprocess.run(["sudo", "restorecon", "-v", str(ENV_FILE)], check=False)


def install_linux():
    _fix_selinux_context()
    service_file = Path(f"/etc/systemd/system/{SERVICE_NAME}.service")
    unit = f"""[Unit]
Description=Power Tracker Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User={os.environ.get("USER", "root")}
WorkingDirectory={REPO_DIR}
EnvironmentFile={ENV_FILE}
ExecStart={PYTHON} -m power_tracker.main
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    print(f"Writing {service_file} ...")
    subprocess.run(
        ["sudo", "tee", str(service_file)],
        input=unit,
        text=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", SERVICE_NAME], check=True)
    subprocess.run(["sudo", "systemctl", "restart", SERVICE_NAME], check=True)
    print("Done.")
    subprocess.run(["sudo", "systemctl", "status", SERVICE_NAME, "--no-pager"])


def uninstall_linux():
    subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME])
    subprocess.run(["sudo", "systemctl", "disable", SERVICE_NAME])
    subprocess.run(["sudo", "rm", "-f", f"/etc/systemd/system/{SERVICE_NAME}.service"])
    subprocess.run(["sudo", "systemctl", "daemon-reload"])
    print("Uninstalled.")


# ── macOS ────────────────────────────────────────────────────────────────────

def install_macos():
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"com.{SERVICE_NAME}.plist"

    env_xml = "\n".join(
        f"            <key>{k}</key><string>{v}</string>"
        for k, v in _parse_env().items()
    )

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON}</string>
        <string>-m</string>
        <string>power_tracker.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{REPO_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
{env_xml}
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/Library/Logs/{SERVICE_NAME}.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/Library/Logs/{SERVICE_NAME}.err</string>
</dict>
</plist>
"""
    plist_path.write_text(plist)
    print(f"Written {plist_path}")
    subprocess.run(["launchctl", "unload", str(plist_path)], stderr=subprocess.DEVNULL)
    subprocess.run(["launchctl", "load", "-w", str(plist_path)], check=True)
    print(f"Done. Logs: ~/Library/Logs/{SERVICE_NAME}.log")


def uninstall_macos():
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"com.{SERVICE_NAME}.plist"
    subprocess.run(["launchctl", "unload", str(plist_path)], stderr=subprocess.DEVNULL)
    plist_path.unlink(missing_ok=True)
    print("Uninstalled.")


# ── Windows ──────────────────────────────────────────────────────────────────

def install_windows():
    print("Registering scheduled task (runs at startup as SYSTEM) ...")
    subprocess.run(
        f'schtasks /Create /TN "{SERVICE_NAME}" /TR '
        f'"{PYTHON} -m power_tracker.main" '
        f'/SC ONSTART /RU SYSTEM /RL HIGHEST /F',
        shell=True,
        check=True,
    )
    for k, v in _parse_env().items():
        subprocess.run(
            f'setx /M {k} "{v}"',
            shell=True,
            stdout=subprocess.DEVNULL,
        )
    print("Done. Start now with:")
    print(f'  schtasks /Run /TN "{SERVICE_NAME}"')


def uninstall_windows():
    subprocess.run(f'schtasks /Delete /TN "{SERVICE_NAME}" /F', shell=True)
    print("Uninstalled.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action not in ("install", "uninstall"):
        print("Usage: install_server.py [install|uninstall]")
        sys.exit(1)

    _check_env()
    _install_deps()
    system = platform.system().lower()

    dispatch = {
        "linux":   (install_linux,   uninstall_linux),
        "darwin":  (install_macos,   uninstall_macos),
        "windows": (install_windows, uninstall_windows),
    }

    if system not in dispatch:
        print(f"Unsupported OS: {system}")
        sys.exit(1)

    install_fn, uninstall_fn = dispatch[system]
    if action == "install":
        print(f"Installing {SERVICE_NAME} on {system} ...")
        install_fn()
    else:
        print(f"Uninstalling {SERVICE_NAME} on {system} ...")
        uninstall_fn()


if __name__ == "__main__":
    main()
