#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
BASE = Path(__file__).resolve().parent


MODULES = [
    {
        "key": "1",
        "name": "Network Automation",
        "tasks": "1–2",
        "module": "src.automate",
        "description": "Push configuration commands to network devices (VyOS, Arista, MikroTik) over SSH with Telnet fallback.",
    },
    {
        "key": "2",
        "name": "CPU Monitor",
        "tasks": "3",
        "module": "src.cpu_monitor",
        "description": "Real-time VyOS router CPU utilisation profiler with matplotlib trend graph.",
    },
    {
        "key": "3",
        "name": "Packet Sniffer",
        "tasks": "4",
        "module": "src.packet_sniffer",
        "description": "Scapy-based live packet capture with protocol inspection on any interface.",
    },
    {
        "key": "4",
        "name": "End Device Manager",
        "tasks": "5",
        "module": "src.end_device_manager",
        "description": "Bulk SSH command execution, hostname changes, SCP file transfers, and interactive shell.",
    },
    {
        "key": "5",
        "name": "Chat Server",
        "tasks": "—",
        "module": "src.chat.server",
        "description": "Multi-client chat server with file upload/download, nicknames, and live relay.",
    },
    {
        "key": "6",
        "name": "Chat Client",
        "tasks": "—",
        "module": "src.chat.client",
        "description": "Connect to the chat server — send messages, transfer files, download uploads.",
    },
    {
        "key": "7",
        "name": "Legacy Arrow-Key Menu",
        "tasks": "—",
        "module": "src.menu",
        "description": "Original launcher with arrow-key navigation (↑/↓ → Enter).",
    },
    {
        "key": "8",
        "name": "Exit",
        "module": None,
        "description": "Leave the guide.",
    },
]


def draw_welcome():
    console.clear()
    console.print(
        Panel.fit(
            Text(
                "CN451 Network Programming — Final Project",
                justify="center",
                style="bold cyan",
            ),
            subtitle="Configuration Automation & Network Tools",
            border_style="cyan",
        )
    )

    table = Table(show_header=False, show_lines=True, box=None, padding=(0, 2))
    table.add_column("Key", style="bold yellow", width=6)
    table.add_column("Module", style="bold white", width=22)
    table.add_column("Tasks", style="dim", width=6)
    table.add_column("Description")

    for m in MODULES:
        if m["module"] is None:
            continue
        table.add_row(
            f"  [{m['key']}]",
            m["name"],
            m.get("tasks", ""),
            m["description"],
        )

    console.print(table)
    console.print()


def launch_module(module_name):
    console.clear()
    console.print(f"[green]Launching {module_name}...[/]\n")
    try:
        result = subprocess.run(
            [sys.executable, "-m", module_name],
            cwd=str(BASE),
        )
        if result.returncode != 0:
            console.print(
                f"\n[yellow]{module_name} exited with code {result.returncode}[/]"
            )
    except FileNotFoundError:
        console.print(f"\n[bold red]Module not found:[/] {module_name}")
    except OSError as exc:
        console.print(f"\n[bold red]OS error launching {module_name}:[/] {exc}")
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
        return
    except Exception as exc:
        console.print(
            f"\n[bold red]Unexpected error launching {module_name}:[/] {exc}"
        )

    input("\nPress Enter to return to guide...")


def main():
    while True:
        try:
            draw_welcome()
            choice = input("  Select an option [1–8]: ").strip()

            if choice == "8":
                break

            matched = [m for m in MODULES if m["key"] == choice]
            if not matched or matched[0]["module"] is None:
                console.print(
                    "[yellow]Invalid choice. Press Enter to try again.[/]"
                )
                input()
                continue

            launch_module(matched[0]["module"])

        except KeyboardInterrupt:
            console.print("\n[yellow]see you later alligator[/]")
            break
        except Exception as exc:
            console.print(f"\n[bold red]Unexpected error:[/] {exc}")
            input("\nPress Enter to continue...")

    console.clear()
    console.print("[bold cyan]Goodbye![/]")


if __name__ == "__main__":
    main()
