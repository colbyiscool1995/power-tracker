#!/usr/bin/env python3
"""Install power-tracker-client as a background service for the current OS."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent.resolve()
PYTHON = sys.executable
SERVICE_NAME = "power-tracker-client"
ENV_FILE = REPO_DIR / ".env"


def _check_env():
    if not ENV_FILE.exists():
        print(f"ERROR: .env not found at {ENV_FILE}")
        print("Copy .env.example to .env and fill in values.")
        sys.exit(1)


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
Description=Power Tracker Client
After=network.target

[Service]
Type=simple
User={os.environ.get("USER", "root")}
WorkingDirectory={REPO_DIR}
EnvironmentFile={ENV_FILE}
ExecStart={PYTHON} -m power_tracker.client
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

    env_vars = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()

    env_xml = "\n".join(
        f"            <key>{k}</key><string>{v}</string>"
        for k, v in env_vars.items()
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
        <string>power_tracker.client</string>
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
    print("Done. Logs: ~/Library/Logs/power-tracker-client.log")


def uninstall_macos():
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"com.{SERVICE_NAME}.plist"
    subprocess.run(["launchctl", "unload", str(plist_path)], stderr=subprocess.DEVNULL)
    plist_path.unlink(missing_ok=True)
    print("Uninstalled.")


# ── Windows ──────────────────────────────────────────────────────────────────

def install_windows():
    task_cmd = (
        f'schtasks /Create /TN "{SERVICE_NAME}" /TR '
        f'"{PYTHON} -m power_tracker.client" '
        f'/SC ONSTART /RU SYSTEM /RL HIGHEST /F'
    )
    env_file_win = str(ENV_FILE).replace("/", "\\")
    print("Registering scheduled task (runs at startup as SYSTEM) ...")
    subprocess.run(task_cmd, shell=True, check=True)

    # Load .env vars into the system environment for the task
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                subprocess.run(
                    f'setx /M {k.strip()} "{v.strip()}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                )
    print("Done. Task registered. It will start on next reboot.")
    print("To start now: schtasks /Run /TN power-tracker-client")


def uninstall_windows():
    subprocess.run(f'schtasks /Delete /TN "{SERVICE_NAME}" /F', shell=True)
    print("Uninstalled.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action not in ("install", "uninstall"):
        print("Usage: install_client.py [install|uninstall]")
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
        print(f"Installing on {system} ...")
        install_fn()
    else:
        print(f"Uninstalling on {system} ...")
        uninstall_fn()


if __name__ == "__main__":
    main()
