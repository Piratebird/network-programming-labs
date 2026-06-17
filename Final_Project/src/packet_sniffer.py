#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

console = Console()


def load_scapy_sniff():
    try:
        from scapy.all import sniff

        return sniff
    except ImportError:
        project_python = Path(__file__).resolve().parent / "venv" / "bin" / "python"
        if (
            project_python.exists()
            and Path(sys.executable).resolve() != project_python.resolve()
        ):
            console.print(
                "[yellow]Scapy is not available in this Python interpreter.[/] "
                f"Retrying with project venv: {project_python}"
            )
            os.execv(str(project_python), [str(project_python), *sys.argv])
        raise


def prompt_sudo_reexec(extra_args=None):
    if os.geteuid() == 0:
        return False
    answer = Prompt.ask(
        "[yellow]Permission denied.[/] Re-run with [bold]sudo[/]?",
        choices=["y", "n"],
        default="y",
    )
    if answer == "y":
        sudo = shutil.which("sudo")
        if sudo:
            args = [sudo, sys.executable, *sys.argv]
            if extra_args:
                args.extend(extra_args)
            os.execv(sudo, args)
        else:
            console.print("[red]sudo not found on this system.[/]")
            return False
    return False


def sniff_packets(interface, count, bpf_filter):
    try:
        sniff = load_scapy_sniff()
    except ImportError:
        console.print(
            "[bold red]Scapy is not installed.[/] Install dependencies with: "
            "python -m pip install -r requirements.txt"
        )
        return
    except PermissionError:
        prompt_sudo_reexec()
        return

    table = Table(title=f"Packet Sniffer: {interface}", show_lines=True)
    table.add_column("Time")
    table.add_column("Source")
    table.add_column("Destination")
    table.add_column("Protocol")
    table.add_column("Length")

    def handle_packet(packet):
        timestamp = datetime.now().strftime("%H:%M:%S")
        src = getattr(packet, "src", "-")
        dst = getattr(packet, "dst", "-")
        proto = packet.lastlayer().name if packet.lastlayer() else packet.name
        table.add_row(timestamp, str(src), str(dst), proto, str(len(packet)))
        console.clear()
        console.print(table)

    try:
        console.print(
            f"[cyan]Sniffing {count} packet(s) on {interface}"
            f"{f' with filter {bpf_filter!r}' if bpf_filter else ''}...[/]"
        )
        sniff(
            iface=interface,
            count=count,
            filter=bpf_filter or None,
            prn=handle_packet,
            store=False,
        )
    except PermissionError:
        prompt_sudo_reexec(["-i", interface, "-c", str(count)])
    except OSError as exc:
        console.print(f"[bold red]Interface or capture error:[/] {exc}")
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")


def list_interfaces():
    if sys.platform == "linux":
        net_dir = Path("/sys/class/net")
        if not net_dir.is_dir():
            return None
        interfaces = sorted(
            e.name for e in net_dir.iterdir() if e.name != "lo"
        )
        if not interfaces:
            interfaces = sorted(e.name for e in net_dir.iterdir())
        return interfaces

    if sys.platform == "win32":
        return _list_interfaces_windows()

    return None


def _list_interfaces_windows():
    try:
        output = subprocess.check_output(
            ["ipconfig"], text=True, stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    interfaces = []
    for line in output.splitlines():
        m = re.match(r"^([A-Za-z].*?):", line)
        if m:
            name = m.group(1).strip()
            if name and "Loopback" not in name and "Teredo" not in name:
                interfaces.append(name)
    return sorted(interfaces) if interfaces else None


def choose_interface(interfaces):
    console.print("[cyan]Available network interfaces:[/]")
    for i, iface in enumerate(interfaces, 1):
        console.print(f"  {i}. {iface}")
    choice = Prompt.ask(
        "[cyan]Select interface[/]",
        choices=[str(i) for i in range(1, len(interfaces) + 1)],
        default="1",
    )
    return interfaces[int(choice) - 1]


def main():
    parser = argparse.ArgumentParser(description="Task 4 Scapy packet sniffer")
    parser.add_argument(
        "-i", "--interface", help="Interface name, for example eth0"
    )
    parser.add_argument(
        "-c", "--count", type=int, default=None, help="Number of packets to capture"
    )
    parser.add_argument(
        "-f",
        "--filter",
        default="",
        help="Optional BPF filter, for example 'tcp port 5050'",
    )
    args = parser.parse_args()

    interface = args.interface
    if not interface:
        interfaces = list_interfaces()
        if interfaces:
            interface = choose_interface(interfaces)
        else:
            console.print(
                "[bold red]No interface specified and unable to list interfaces.[/] "
                "Use -i to specify an interface."
            )
            return

    count = args.count if args.count is not None else None
    if count is None or count <= 0:
        while True:
            raw = Prompt.ask(
                "[cyan]Number of packets to capture[/]", default="10"
            )
            try:
                count = int(raw)
                if count > 0:
                    break
                console.print("[red]Must be greater than zero.[/]")
            except ValueError:
                console.print("[red]Enter a valid number.[/]")

    sniff_packets(interface, count, args.filter)


if __name__ == "__main__":
    main()
