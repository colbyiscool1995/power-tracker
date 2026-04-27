import os
import socket


def get_system_name() -> str:
    return os.environ.get("SYSTEM_NAME", socket.gethostname())


def get_local_ip() -> str:
    local_ip = os.environ.get("LOCAL_IP")
    if local_ip:
        return local_ip

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
