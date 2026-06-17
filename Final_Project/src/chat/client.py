#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import socket
import sys
import threading
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

HOST = "192.168.2.100"
PORT = 5050
BUFFER_SIZE = 4096
MAX_FILE_SIZE = 150 * 1024
HEADER_SIZE = 64
MAX_JSON_SIZE = 400 * 1024
DOWNLOAD_DIR = Path("storage/downloads")
console = Console()

# Ensure the client's download directory exists locally
DOWNLOAD_DIR.mkdir(exist_ok=True)

send_lock = threading.Lock()
running = True

### Network Primitives (Matching Server Headers) ###


def send_json(sock, data):
    """Encodes JSON data and prefixes it with a padded 64-byte length header."""
    global running
    with send_lock:
        try:
            data.setdefault("timestamp", datetime.now().strftime("%H:%M:%S"))
            message = json.dumps(data).encode("utf-8")
            msg_length = len(message)
            if msg_length > MAX_JSON_SIZE:
                raise ValueError("Message is too large for the chat protocol.")
            send_length = str(msg_length).encode("utf-8")
            send_length += b" " * (HEADER_SIZE - len(send_length))

            sock.sendall(send_length)
            sock.sendall(message)
        except (OSError, ValueError) as e:
            console.print(f"\n[bold red]Error sending message:[/] {e}")
            running = False


def receive_exact(sock, size):
    chunks = []
    bytes_received = 0
    while bytes_received < size:
        chunk = sock.recv(min(size - bytes_received, BUFFER_SIZE))
        if not chunk:
            return None
        chunks.append(chunk)
        bytes_received += len(chunk)
    return b"".join(chunks)


def receive_loop(sock):
    """Background thread that continuously reads formatted packets from the server."""
    global running
    while running:
        try:
            header = receive_exact(sock, HEADER_SIZE)
            if not header:
                console.print("\n[yellow]Connection closed by server.[/]")
                break

            header_text = header.decode("utf-8", errors="replace").strip()
            if not header_text.isdigit():
                raise ConnectionError("Invalid protocol header from server.")

            msg_length = int(header_text)
            if msg_length <= 0 or msg_length > MAX_JSON_SIZE:
                raise ConnectionError("Server payload size is invalid or too large.")

            payload_bytes = receive_exact(sock, msg_length)
            if payload_bytes is None:
                raise ConnectionError("Incomplete message payload received.")

            payload = payload_bytes.decode("utf-8")
            message = json.loads(payload)

            if "file" in message:
                handle_incoming_file(message["file"])
            else:
                print_message(message)

        except (ConnectionError, OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
            if running:
                console.print(f"\n[bold red]Error receiving data:[/] {e}")
            break
    running = False


### Client Logic and Command Handling ###


def connect_and_register(host, port):
    """Establishes connection and transmits initial username packet."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)
    sock.connect((host, port))
    username = input("Enter your username: ").strip()
    if not username:
        raise ValueError("Username cannot be empty.")

    send_json(sock, {"username": username})
    sock.settimeout(None)
    return sock


def send_upload(sock, file_path):
    """Reads a local file, confirms size compliance, and uploads as a hex payload."""
    if not file_path.is_file():
        console.print(f"[bold red]File not found:[/] {file_path}")
        return
    if file_path.stat().st_size > MAX_FILE_SIZE:
        console.print(f"[bold red]File is too large[/] (max {MAX_FILE_SIZE} bytes).")
        return

    try:
        with file_path.open("rb") as f:
            file_data = f.read()

        # Check raw file size, not hex string size
        if len(file_data) > MAX_FILE_SIZE:
            print(
                f"Error: File is {len(file_data)} bytes. Max allowed is 153,600 bytes."
            )
            return

        # Aligned with server: expects 'file_upload' dict containing 'name' & 'content' hex
        payload = {"file_upload": {"name": file_path.name, "content": file_data.hex()}}
        send_json(sock, payload)
        console.print(f"[cyan]Uploading {file_path.name}... waiting for server verification.[/]")
    except (OSError, ValueError) as e:
        console.print(f"[bold red]Error processing file for upload:[/] {e}")


def handle_incoming_file(file_info):
    """Processes downloaded hex strings sent from the server and writes to disk cleanly."""
    # \r resets the cursor to start of line, \033[K clears any old residue (like "> ")
    prefix = "\r\033[K"
    try:
        filename = file_info["name"]
        file_bytes = bytes.fromhex(file_info["content"])
        target_path = DOWNLOAD_DIR / filename

        with open(target_path, "wb") as f:
            f.write(file_bytes)
        console.print(f"{prefix}[green][SYSTEM][/green] File downloaded to: {target_path}")
    except (OSError, ValueError, KeyError) as e:
        console.print(f"{prefix}[bold red][ERROR][/bold red] Failed to save downloaded file: {e}")

    # Redraw a clean prompt for the main input thread seamlessly
    print("> ", end="", flush=True)


def print_message(message):
    """Parses structural JSON payloads and uses ANSI sequences to prevent prompt collisions."""
    prefix = "\r\033[K"
    stamp = message.get("timestamp", datetime.now().strftime("%H:%M:%S"))

    if "system" in message:
        console.print(f"{prefix}[dim]{stamp}[/dim] [cyan][SYSTEM][/cyan] {message.get('message', '')}")
    elif "error" in message:
        console.print(f"{prefix}[dim]{stamp}[/dim] [bold red][ERROR][/bold red] {message.get('error', '')}")
    elif "chat" in message:
        chat_data = message["chat"]
        console.print(f"{prefix}[dim]{stamp}[/dim] [bold]{chat_data.get('from')}[/bold]: {chat_data.get('message', '')}")
    elif "private_message" in message:
        pm_data = message["private_message"]
        console.print(f"{prefix}[dim]{stamp}[/dim] [magenta][PM from {pm_data.get('from')}][/magenta] {pm_data.get('message', '')}")
    elif "users" in message:
        console.print(f"{prefix}[dim]{stamp}[/dim] [green][ACTIVE USERS][/green] {', '.join(message['users'])}")
    elif "files" in message:
        files = ', '.join(message['files']) if message['files'] else 'No files found.'
        console.print(f"{prefix}[dim]{stamp}[/dim] [cyan][SERVER FILES][/cyan] {files}")
    elif "message" in message:
        console.print(f"{prefix}[dim]{stamp}[/dim] [cyan][SERVER][/cyan] {message.get('message', '')}")
    else:
        console.print(f"{prefix}[dim]{stamp}[/dim] [yellow][RAW DATA][/yellow] {message}")

    # Keep the prompt cleanly pinned to the very bottom of the window
    print("> ", end="", flush=True)


def print_help():
    table = Table(title="Command Menu", show_header=False, box=None)
    table.add_column("Command", style="bold cyan")
    table.add_column("Action")
    table.add_row("/help", "Display menu options")
    table.add_row("/quit", "Disconnect safely from server")
    table.add_row("/users", "List all online usernames")
    table.add_row("/pm <username> <message>", "Send a private message")
    table.add_row("/rps <username>", "Challenge an online player to RPS")
    table.add_row("/files", "List files hosted on the server")
    table.add_row("/upload <filepath>", "Upload a local file under 150 KB")
    table.add_row("/download <filename>", "Download an uploaded server file")
    console.print(Panel(table, border_style="cyan"))
    console.print("[dim]During RPS, type rock, paper, or scissors. Other text is broadcast.[/dim]")


def prompt_host(default_host=HOST):
    raw = Prompt.ask("[cyan]Server IP[/]", default=default_host)
    return raw.strip() or default_host


def prompt_port(default_port=PORT):
    while True:
        raw = Prompt.ask("[cyan]Server port[/]", default=str(default_port))
        try:
            p = int(raw)
            if 1 <= p <= 65535:
                return p
            console.print("[red]Port must be between 1 and 65535.[/]")
        except ValueError:
            console.print("[red]Enter a valid port number.[/]")


def ensure_admin():
    if sys.platform == "win32":
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
        console.print("[yellow]Not running as administrator.[/]")
        answer = Prompt.ask(
            "[yellow]Re-run as administrator?[/]", choices=["y", "n"], default="y"
        )
        if answer == "y":
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()
    elif sys.platform == "linux" and os.geteuid() != 0:
        console.print("[yellow]Not running as root. Some features may require privileges.[/]")


def main():
    global running
    parser = argparse.ArgumentParser(description="CN451 TCP chat client")
    parser.add_argument("host", nargs="?", default=None, help="Server IP")
    parser.add_argument("port", nargs="?", type=int, default=None, help="Server TCP port")
    args = parser.parse_args()
    host = args.host if args.host else prompt_host()
    port = args.port if args.port else prompt_port()

    ensure_admin()

    try:
        sock = connect_and_register(host, port)
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Could not connect to or register with {host}:{port}:[/] {exc}")
        return

    print_help()

    # Print the very first input indicator explicitly before starting the receive thread
    print("> ", end="", flush=True)

    receiver = threading.Thread(target=receive_loop, args=(sock,), daemon=True)
    receiver.start()

    try:
        while running:
            # Change standard input() to pass an empty string because our print loop manages the prompt
            line = input("").strip()
            if not line:
                # If they just hit enter, redraw a fresh prompt line safely
                print("> ", end="", flush=True)
                continue

            # Command routing logic
            if line == "/help":
                print_help()
                print("> ", end="", flush=True)
                continue

            # Intercept Rock Paper Scissors gameplay choices directly
            if line.lower() in ["rock", "paper", "scissors"]:
                send_json(sock, {"rps_choice": line.lower()})
                continue

            # Intercept upload execution commands
            if line.startswith("/upload "):
                _, _, file_path_str = line.partition(" ")
                send_upload(sock, Path(file_path_str.strip()).expanduser())
                continue

            # Route everything else under uniform "message" envelope
            send_json(sock, {"message": line})

            if line == "/quit":
                running = False
                break
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]see you later alligator[/]")
    finally:
        running = False
        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()
