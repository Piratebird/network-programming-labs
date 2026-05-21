import json
import socket
import threading
from pathlib import Path

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
UPLOAD_DIR = Path("uploads")

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
            # Pull either the remaining chunk size or standard buffer increments
            chunk = sock.recv(min(size - bytes_received, 4096))
            if not chunk:
                return None

            chunks.append(chunk)
            bytes_received += len(chunk)
        except OSError:
            # socket error likely means client disconnected mid-message
            return None
    return b"".join(chunks)


def receive_json(sock):
    """Safely extracts full application payloads via sequential exact byte collection."""
    try:
        # Pull exactly 64 bytes for the fixed length header
        header_bytes = receive_exact(sock, 64)
        if not header_bytes:
            return None

        msg_length = int(header_bytes.decode("utf-8").strip())

        # Pull exactly the payload body size specified by the header
        msg_bytes = receive_exact(sock, msg_length)
        if not msg_bytes:
            return None

        return json.loads(msg_bytes.decode("utf-8"))
    except Exception as e:
        # Prints internal parsing bugs to server terminal without killing the connection loop
        print(f"[DEBUG ERROR] Broken JSON extraction sequence: {e}")
        return None


def send_json_to_sock(sock, data):
    message = json.dumps(data).encode("utf-8")
    msg_length = len(message)
    send_length = str(msg_length).encode("utf-8")
    send_length += b" " * (64 - len(send_length))
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
    username_msg = receive_json(conn)
    if not username_msg or "username" not in username_msg:
        print(f"[DISCONNECT] {address} did not send a valid username.")
        conn.close()
        return None

    username = username_msg["username"].strip()
    with state_lock:
        if username in clients_by_name or not username:
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
                send_json_to_client(
                    clients_by_name[opponent],
                    {"message": "Your opponent has disconnected. Game over."},
                )
    try:
        client.sock.close()  # FIXED: Actually executed the close call
    except:
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
    files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
    send_json_to_client(client, {"files": files})


def handle_download(client, filename):
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
                # Task 3: Save file chunks uploaded from clients
                file_info = msg["file_upload"]
                fname = Path(file_info["name"]).name  # Basic path traversal safety

                try:
                    # Convert hex back to binary data first
                    fdata = bytes.fromhex(file_info["content"])

                    if len(fdata) > 153600:  # 150 KB Guardrail
                        send_json_to_client(
                            client, {"error": "File exceeds strict 150KB limit."}
                        )
                        continue  # FIX 1: Jump back to the top of the loop, keeping the socket OPEN

                    with open(UPLOAD_DIR / fname, "wb") as f:
                        f.write(fdata)
                    send_json_to_client(
                        client, {"message": f"Successfully uploaded {fname}."}
                    )
                except Exception as upload_error:
                    send_json_to_client(
                        client, {"error": f"Upload process failed: {str(upload_error)}"}
                    )
                    continue  # FIX 2: Prevent bad hex formatting from crashing the client thread
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


def start_server():
    UPLOAD_DIR.mkdir(exist_ok=True)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()

    print(logo)
    print(f"\nCN451 chat server listening on {HOST}:{PORT}")

    try:
        while True:
            client_sock, address = server_sock.accept()
            thread = threading.Thread(
                target=handle_client, args=(client_sock, address), daemon=True
            )
            thread.start()
    except KeyboardInterrupt:
        print("\nServer shutting down gracefully.")
    finally:
        server_sock.close()


if __name__ == "__main__":
    start_server()
