import telnetlib
import time
import json
import os
import re
from urllib.parse import urlparse
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEVICES_FILE = os.path.join(BASE_DIR, "devices.json")

PROMPT_REGEX = re.compile(rb"[>#]\s*$")
LOCAL_CONSOLE_HOSTS = {"", "0.0.0.0", "127.0.0.1", "localhost"}
DEFAULT_GNS3_SERVER_URL = "http://100.95.123.100:3080"


class ConsoleHarvesterError(Exception):
    pass


def load_devices():
    if not os.path.exists(DEVICES_FILE):
        raise ConsoleHarvesterError("devices.json not found")

    with open(DEVICES_FILE, "r") as f:
        return json.load(f)


def _resolve_console_host(host: str, server_url: Optional[str]) -> str:
    """
    Normalize local console binds to the GNS3 server host.
    """
    if host in LOCAL_CONSOLE_HOSTS:
        resolved_server_url = server_url or os.environ.get(
            "GNS3_SERVER_URL", DEFAULT_GNS3_SERVER_URL
        )
        parsed = urlparse(resolved_server_url)
        return parsed.hostname or "127.0.0.1"
    return host


def wait_for_prompt(tn, timeout=300):
    """
    Read until a Cisco-style prompt appears.
    Sends newline periodically to advance past banners.
    """
    buffer = b""
    start = time.time()

    while time.time() - start < timeout:
        try:
            chunk = tn.read_very_eager()
            if chunk:
                buffer += chunk
                if PROMPT_REGEX.search(buffer):
                    return buffer
            else:
                tn.write(b"\n")
                time.sleep(0.5)
        except EOFError:
            break

    raise ConsoleHarvesterError("Timeout waiting for device prompt")


def send_and_wait(tn, command, timeout=20):
    """
    Send a command and wait for the prompt to return.
    """
    tn.write(command.encode("ascii") + b"\n")
    buffer = b""
    start = time.time()

    while time.time() - start < timeout:
        chunk = tn.read_very_eager()
        if chunk:
            buffer += chunk
            if PROMPT_REGEX.search(buffer):
                return buffer
        else:
            time.sleep(0.2)

    raise ConsoleHarvesterError(
        f"Timeout waiting for prompt after command: {command}")


def capture_running_config(device_name: str, server_url: Optional[str] = None):
    devices = load_devices()

    if device_name not in devices:
        raise ConsoleHarvesterError(f"Unknown device: {device_name}")

    host = devices[device_name]["host"]
    port = devices[device_name]["port"]

    host = _resolve_console_host(host, server_url)

    tn = telnetlib.Telnet(host, port, timeout=10)

    try:
        # Get to initial prompt
        wait_for_prompt(tn)

        # Enter enable mode (assumes no enable password)
        send_and_wait(tn, "enable")

        # Disable paging
        send_and_wait(tn, "terminal length 0")

        # Run show running-config
        tn.write(b"show running-config\n")

        output = b""
        start = time.time()

        while time.time() - start < 60:
            chunk = tn.read_very_eager()
            if chunk:
                output += chunk
                if PROMPT_REGEX.search(output):
                    break
            else:
                time.sleep(0.2)

        if not output:
            raise ConsoleHarvesterError(
                "No output received from show running-config")

        decoded = output.decode(errors="ignore")

        # Strip echoed command and trailing prompt
        cleaned = _clean_config_output(decoded)

        if not cleaned.strip():
            raise ConsoleHarvesterError("Captured config is empty")

        return cleaned

    finally:
        try:
            tn.close()
        except Exception:
            pass


def _clean_config_output(raw_text):
    """
    Remove command echoes and trailing prompt lines.
    """
    lines = raw_text.splitlines()

    cleaned_lines = []
    recording = False

    for line in lines:
        if line.strip().startswith("version") or line.strip().startswith("hostname"):
            recording = True

        if recording:
            if PROMPT_REGEX.search(line.encode()):
                break
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines) + "\n"
