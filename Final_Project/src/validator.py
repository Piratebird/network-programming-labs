#!/usr/bin/env python3

import ipaddress
from pathlib import Path


VALID_DEVICE_TYPES = {"vyos", "arista_eos", "mikrotik_routeros"}


def _iter_data_lines(filename):
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(f"Missing required data file: {filename}")

    with path.open("r", encoding="utf-8") as handle:
        for line_num, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if line and not line.startswith("#"):
                yield line_num, line


def load_and_validate_devices(filename="config/devices.txt"):
    """Reads devices file, validates IP structural integrity, returns structured dict."""
    devices = {}
    for line_num, line in _iter_data_lines(filename):
        parts = [item.strip() for item in line.split(",")]
        if len(parts) != 3:
            print(f"[WARNING] Skipping malformed device line {line_num} in {filename}")
            continue

        name, ip, dev_type = parts
        try:
            ipaddress.IPv4Address(ip)
        except ValueError:
            print(f"[WARNING] Skipping invalid IPv4 address on line {line_num}: {ip}")
            continue

        if not name:
            print(f"[WARNING] Skipping unnamed device on line {line_num} in {filename}")
            continue
        if dev_type not in VALID_DEVICE_TYPES:
            print(f"[WARNING] Device {name} uses untested Netmiko type: {dev_type}")

        devices[name] = {"ip": ip, "type": dev_type}

    if not devices:
        raise ValueError(f"No valid devices found in {filename}")
    return devices


def load_credentials(filename="config/login.txt"):
    """Reads credentials file and maps them to device entries."""
    creds = {}
    for line_num, line in _iter_data_lines(filename):
        parts = [item.strip() for item in line.split(",")]
        if len(parts) != 3:
            print(f"[WARNING] Skipping malformed credential line {line_num} in {filename}")
            continue

        name, user, passwd = parts
        if not all([name, user, passwd]):
            print(f"[WARNING] Skipping incomplete credential line {line_num} in {filename}")
            continue
        creds[name] = {"username": user, "password": passwd}

    if not creds:
        raise ValueError(f"No valid credentials found in {filename}")
    return creds


def load_commands(filename="config/commands.txt"):
    """Reads commands file and extracts list of actions per device name."""
    cmds = {}
    for line_num, line in _iter_data_lines(filename):
        if ":" not in line:
            print(f"[WARNING] Skipping command line without ':' on line {line_num}")
            continue

        name, cmd_string = line.split(":", 1)
        cmd_list = [command.strip() for command in cmd_string.split("|") if command.strip()]
        if not name.strip() or not cmd_list:
            print(f"[WARNING] Skipping empty command mapping on line {line_num}")
            continue
        cmds[name.strip()] = cmd_list

    if not cmds:
        raise ValueError(f"No valid command mappings found in {filename}")
    return cmds
