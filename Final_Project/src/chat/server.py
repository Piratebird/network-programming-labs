#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

console = Console()

logo = r"""
 _______           _______  _______  _______  _______ _________
(  ____ \|\     /|(  ___  )(  ____ )(  ____ )(  ___  )\__   __/
| (    \/| )   ( || (   ) || (    )|| (    )|| (   ) |   ) (   
| |      | (___) || (___) || (____)|| (____)|| |   | |   | |   
| |      |  ___  ||  ___  ||     __)|     __)| |   | |   | |   
| |      | (   ) || (   ) || (\ (   | (\ (   | |   | |   | |   
| (____/\| )   ( || )   ( || ) \ \__| ) \ \__| (___) |   | |   
(_______/|/     \||/     \||/   \__/|/   \__/(_______)   )_(   
                                                               """

HOST = "0.0.0.0"
PORT = 5050
UPLOAD_DIR = Path("storage/uploads")
HEADER_SIZE = 64
MAX_JSON_SIZE = 400 * 1024
MAX_FILE_SIZE = 150 * 1024

### interface helpers ###


def list_interfaces_with_ips():
    if sys.platform == "linux":
        return _linux_interfaces()
    if sys.platform == "win32":
        return _windows_interfaces()
    return []


def _linux_interfaces():
    try:
        output = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show"], text=True, stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    interfaces = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            name = parts[1].strip()
            ip_cidr = parts[3].strip()
            ip = ip_cidr.split("/")[0]
            if name != "lo":
                interfaces.append((name, ip))
    return interfaces


def _windows_interfaces():
    try:
        output = subprocess.check_output(
            ["ipconfig"], text=True, stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    interfaces = []
    current_name = None
    for line in output.splitlines():
        m = re.match(r"^([A-Za-z].*?):", line)
        if m:
            current_name = m.group(1).strip()
        elif current_name and "IPv4" in line:
            ip_m = re.search(r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
            if ip_m and "Loopback" not in current_name and "Teredo" not in current_name:
                interfaces.append((current_name, ip_m.group(1)))
                current_name = None
    return interfaces


def choose_interface():
    interfaces = list_interfaces_with_ips()
    if not interfaces:
        return None

    console.print("[cyan]Available network interfaces:[/]")
    for i, (name, ip) in enumerate(interfaces, 1):
        console.print(f"  {i}. {name} ({ip})")
    choice = Prompt.ask(
        "[cyan]Select interface to bind[/]",
        choices=[str(i) for i in range(1, len(interfaces) + 1)],
        default="1",
    )
    return interfaces[int(choice) - 1][1]


def prompt_port(default_port=PORT):
    while True:
        raw = Prompt.ask("[cyan]Port to listen on[/]", default=str(default_port))
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
        answer = Prompt.ask(
            "[yellow]Not running as root.[/] Re-run with [bold]sudo[/]?",
            choices=["y", "n"],
            default="y",
        )
        if answer == "y":
            sudo = shutil.which("sudo")
            if sudo:
                os.execv(sudo, [sudo, sys.executable, *sys.argv])
            else:
                console.print("[red]sudo not found.[/]")


### classes ###


class Client:
    def __init__(self, sock, address, username):
        self.sock = sock
        self.address = address
        self.username = username
        self.send_lock = threading.Lock()


class RPS:
    choices = {"rock", "paper", "scissors"}
    beats = {
        "rock": "scissors",
        "paper": "rock",
        "scissors": "paper",
    }

    def __init__(self, player1, player2):
        self.players = [player1, player2]
        self.scores = {player1: 0, player2: 0}
        self.choices_this_round = {}  # FIXED: Correct variable name initialization
        self.scored_rounds = 0  # FIXED: Added missing tracking counter
        self.game_lock = threading.Lock()

    def oponent_of(self, player):
        return self.players[1] if self.players[0] == player else self.players[0]

    def add_choice(self, username, choice):
        with self.game_lock:  # Protected state changes
            self.choices_this_round[username] = choice
            if len(self.choices_this_round) < 2:
                return None

            p1, p2 = self.players
            c1 = self.choices_this_round[p1]
            c2 = self.choices_this_round[p2]
            self.choices_this_round = {}

            if c1 == c2:
                return {
                    "tie": True,
                    "message": f"RPS tie: both chose {c1}. Replay the round.",
                    "winner": None,
                    "game_over": False,
                }

            if self.beats[c1] == c2:
                winner = p1
            else:
                winner = p2

            self.scored_rounds += 1
            self.scores[winner] += 1
            game_over = self.scores[winner] == 3 or self.scored_rounds == 5

            return {
                "tie": False,
                "message": (
                    f"RPS round {self.scored_rounds}: {p1} chose {c1}, "
                    f"{p2} chose {c2}. {winner} wins this round. "
                    f"Score: {p1} {self.scores[p1]} - {p2} {self.scores[p2]}."
                ),
                "winner": winner,
                "game_over": game_over,
            }


# Global Application State Variables
clients_by_name = {}
clients_by_socket = {}
games_by_player = {}
state_lock = threading.Lock()

### network primitives ###


def receive_exact(sock, size):
    """Loops until exactly 'size' bytes are extracted from the stream."""
    chunks = []
    bytes_received = 0
    while bytes_received < size:
        try:
            chunk = sock.recv(min(size - bytes_received, 4096))
            if not chunk:
                return None

            chunks.append(chunk)
            bytes_received += len(chunk)
        except (TimeoutError, OSError):
            return None
    return b"".join(chunks)


def receive_json(sock):
    """Safely extracts full application payloads via sequential exact byte collection."""
    try:
        header_bytes = receive_exact(sock, HEADER_SIZE)
        if not header_bytes:
            return None

        header_text = header_bytes.decode("utf-8", errors="replace").strip()
        if not header_text.isdigit():
            return {"error": "Invalid protocol header."}

        msg_length = int(header_text)
        if msg_length <= 0 or msg_length > MAX_JSON_SIZE:
            return {"error": "Protocol payload size is invalid or too large."}

        msg_bytes = receive_exact(sock, msg_length)
        if not msg_bytes:
            return None

        return json.loads(msg_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
        print(f"[PROTOCOL ERROR] Broken JSON extraction sequence: {e}")
        return None


def send_json_to_sock(sock, data):
    data.setdefault("timestamp", datetime.now().strftime("%H:%M:%S"))
    message = json.dumps(data).encode("utf-8")
    msg_length = len(message)
    if msg_length > MAX_JSON_SIZE:
        raise ValueError("Outgoing payload is too large.")
    send_length = str(msg_length).encode("utf-8")
    send_length += b" " * (HEADER_SIZE - len(send_length))
    sock.sendall(send_length)
    sock.sendall(message)


def send_json_to_client(client, data):
    with client.send_lock:
        try:
            send_json_to_sock(client.sock, data)
        except Exception:
            pass  # Client disconnected abruptly


def send_system(client, message):
    send_json_to_client(client, {"system": True, "message": message})


### state management helpers ###


def register_client(conn, address):
    conn.settimeout(120)
    username_msg = receive_json(conn)
    if not username_msg or "username" not in username_msg:
        print(f"[DISCONNECT] {address} did not send a valid username.")
        conn.close()
        return None

    username = str(username_msg["username"]).strip()
    with state_lock:
        if username in clients_by_name or not username or len(username) > 24:
            send_json_to_sock(conn, {"error": "Username already taken or invalid."})
            conn.close()
            return None

        client = Client(conn, address, username)
        clients_by_name[username] = client
        clients_by_socket[conn] = client

    send_json_to_client(client, {"message": f"Welcome, {username}!"})
    print(f"[REGISTERED] {username} connected from {address}")
    return client


def unregister_client(client):
    if not client:
        return
    opponent_client = None
    with state_lock:
        if client.sock in clients_by_socket:
            del clients_by_socket[client.sock]
        if client.username in clients_by_name:
            del clients_by_name[client.username]

        # Handle cleanup if client leaves mid-game
        if client.username in games_by_player:
            game = games_by_player[client.username]
            opponent = game.oponent_of(client.username)
            if client.username in games_by_player:
                del games_by_player[client.username]
            if opponent in games_by_player:
                del games_by_player[opponent]

            if opponent in clients_by_name:
                opponent_client = clients_by_name[opponent]
    if opponent_client:
        send_json_to_client(
            opponent_client,
            {"message": "Your opponent has disconnected. Game over."},
        )
    try:
        client.sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        client.sock.close()
    except OSError:
        pass
    print(f"[DISCONNECT] {client.username} ({client.address}) left server.")


### core operational handlers ###


def broadcast_message(sender_username, message_text):
    """Sends a chat message from one client to all others."""
    with state_lock:
        all_clients = list(clients_by_name.values())
    payload = {"chat": {"from": sender_username, "message": message_text}}
    for client in all_clients:
        send_json_to_client(client, payload)


def handle_rps_choices(client, choice):
    """Processes a player's RPS choice, updates game state, and notifies both players of the result."""
    with state_lock:
        game = games_by_player.get(client.username)
        if not game:
            send_json_to_client(client, {"error": "You are not in an active game."})
            return

    if choice not in RPS.choices:
        send_json_to_client(
            client, {"error": "Invalid choice. Pick rock, paper, or scissors."}
        )
        return

    result = game.add_choice(client.username, choice)
    if not result:
        send_json_to_client(
            client, {"message": "Choice received. Waiting for opponent."}
        )
        return

    opponent = game.oponent_of(client.username)
    with state_lock:
        opp_client = clients_by_name.get(opponent)

    send_json_to_client(client, result)
    if opp_client:
        send_json_to_client(opp_client, result)

    if result["game_over"]:
        with state_lock:
            if client.username in games_by_player:
                del games_by_player[client.username]
            if opponent in games_by_player:
                del games_by_player[opponent]


def handle_users(client):
    with state_lock:
        users = list(clients_by_name.keys())
    send_json_to_client(client, {"users": users})


def handle_private_message(client, target_username, message):
    if not target_username or not message.strip():
        send_json_to_client(client, {"error": "Usage: /pm <username> <message>"})
        return
    with state_lock:
        target_client = clients_by_name.get(target_username)
    if not target_client:
        send_json_to_client(client, {"error": f"User '{target_username}' not found."})
        return
    send_json_to_client(
        target_client,
        {"private_message": {"from": client.username, "message": message}},
    )


def handle_rps_start(client, target_username):
    if not target_username:
        send_json_to_client(client, {"error": "Usage: /rps <username>"})
        return
    if client.username == target_username:
        send_json_to_client(client, {"error": "You can't challenge yourself."})
        return

    with state_lock:
        target_client = clients_by_name.get(target_username)
        if not target_client:
            send_json_to_client(
                client, {"error": f"User '{target_username}' not found."}
            )
            return
        if client.username in games_by_player:
            send_json_to_client(client, {"error": "You are already in a game."})
            return
        if target_username in games_by_player:
            send_json_to_client(
                client, {"error": f"{target_username} is already in a game."}
            )
            return

        game = RPS(client.username, target_username)
        games_by_player[client.username] = game
        games_by_player[target_username] = game

    send_json_to_client(
        client,
        {"message": f"RPS game started with {target_username}. First to 3 wins!"},
    )
    send_json_to_client(
        target_client,
        {"message": f"{client.username} has challenged you to RPS! First to 3 wins!"},
    )


def handle_files(client):
    UPLOAD_DIR.mkdir(exist_ok=True)
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    send_json_to_client(client, {"files": files})


def handle_download(client, filename):
    if not filename:
        send_json_to_client(client, {"error": "Usage: /download <filename>"})
        return
    filename = Path(filename).name
    file_path = UPLOAD_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        send_json_to_client(client, {"error": f"File '{filename}' not found."})
        return
    try:
        with file_path.open("rb") as f:
            content = f.read()
        send_json_to_client(
            client, {"file": {"name": filename, "content": content.hex()}}
        )
    except Exception as e:
        send_json_to_client(client, {"error": f"Failed to read file: {e}"})


def handle_command(client, text):
    command, _, rest = text.partition(" ")
    command = command.lower().strip()

    if command == "/help":
        send_system(
            client,
            "Commands: /help, /quit, /users, /pm <username> <message>, "
            "/rps <username>, /files, /download <filename>",
        )
    elif command == "/users":
        handle_users(client)
    elif command == "/pm":
        target, _, message = rest.partition(" ")
        handle_private_message(client, target, message)
    elif command == "/rps":
        handle_rps_start(client, rest.strip())
    elif command == "/files":
        handle_files(client)
    elif command == "/download":
        handle_download(client, rest.strip())
    elif command == "/quit":
        raise ConnectionError("client quit")
    else:
        send_system(client, f"Unknown command '{command}'. Type /help.")


### thread worker loop ###


def handle_client(conn, address):
    client = register_client(conn, address)
    if not client:
        return

    try:
        while True:
            msg = receive_json(conn)
            if msg is None:
                break

            if "message" in msg:
                text = msg["message"].strip()
                if text.startswith("/"):
                    handle_command(client, text)
                else:
                    broadcast_message(client.username, text)
            elif "rps_choice" in msg:
                handle_rps_choices(client, msg["rps_choice"])
            elif "file_upload" in msg:
                file_info = msg["file_upload"]
                fname = Path(str(file_info.get("name", ""))).name

                try:
                    if not fname:
                        send_json_to_client(client, {"error": "Upload filename is empty."})
                        continue

                    fdata = bytes.fromhex(str(file_info.get("content", "")))

                    if len(fdata) > MAX_FILE_SIZE:
                        send_json_to_client(
                            client, {"error": "File exceeds strict 150KB limit."}
                        )
                        continue

                    with open(UPLOAD_DIR / fname, "wb") as f:
                        f.write(fdata)
                    send_json_to_client(
                        client, {"message": f"Successfully uploaded {fname}."}
                    )
                except Exception as upload_error:
                    send_json_to_client(
                        client, {"error": f"Upload process failed: {str(upload_error)}"}
                    )
                    continue
            else:
                send_json_to_client(
                    client, {"error": "Unknown structural protocol message."}
                )
    except ConnectionError:
        pass
    except Exception as e:
        print(
            f"[ERROR] Exception running client {client.username if client else address}: {e}"
        )
    finally:
        unregister_client(client)


def start_server(host=HOST, port=PORT):
    UPLOAD_DIR.mkdir(exist_ok=True)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen()

    print(logo)
    print(f"\nCN451 chat server listening on {host}:{port}")

    try:
        while True:
            client_sock, address = server_sock.accept()
            thread = threading.Thread(
                target=handle_client, args=(client_sock, address), daemon=True
            )
            thread.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]see you later alligator[/]")
    finally:
        server_sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CN451 TCP chat server")
    parser.add_argument("--host", default=None, help="Bind address")
    parser.add_argument("--port", type=int, default=None, help="TCP port")
    args = parser.parse_args()

    host = args.host
    if not host:
        chosen = choose_interface()
        host = chosen if chosen else HOST

    port = args.port if args.port else prompt_port()

    ensure_admin()
    start_server(host, port)
