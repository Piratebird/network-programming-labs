#!/usr/bin/env python3
"""Interactive project launcher with arrow-key navigation."""

import sys
import subprocess
import termios
import tty
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()


def _getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            _ = sys.stdin.read(1)  # skip '['
            return "\x1b[" + sys.stdin.read(1)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


ITEMS = [
    ("Network Automation", "src.automate"),
    ("CPU Monitor", "src.cpu_monitor"),
    ("Packet Sniffer", "src.packet_sniffer"),
    ("End Device Manager", "src.end_device_manager"),
    ("Chat Server", "src.chat.server"),
    ("Chat Client", "src.chat.client"),
    ("Exit", None),
]


def draw(sel):
    console.clear()
    console.print(
        Panel.fit(
            "[bold cyan]CN451 Network Programming Final Project[/]",
            border_style="cyan",
        )
    )
    console.print("  [dim]↑/↓ navigate  ·  Enter select  ·  Ctrl+C quit[/]\n")
    for i, (label, _) in enumerate(ITEMS):
        if i == sel:
            console.print(f"    [bold white on blue] ▸ {label} [/]")
        else:
            console.print(f"      {label}")


def main():
    sel = 0
    draw(sel)
    base = str(Path(__file__).resolve().parent.parent)

    try:
        while True:
            key = _getch()
            if key == "\x1b[A":
                sel = (sel - 1) % len(ITEMS)
                draw(sel)
            elif key == "\x1b[B":
                sel = (sel + 1) % len(ITEMS)
                draw(sel)
            elif key in ("\r", "\n"):
                label, module = ITEMS[sel]
                if module is None:
                    break
                console.clear()
                console.print(f"[green]Launching {label}...[/]\n")
                subprocess.run([sys.executable, "-m", module], cwd=base)
                input("\nPress Enter to return to menu...")
                draw(sel)
            elif key == "\x03":
                break

    except KeyboardInterrupt:
        pass

    console.clear()
    console.print("[bold yellow]see you later alligator[/]")


if __name__ == "__main__":
    main()
