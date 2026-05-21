import json
import socket
import sys
import threading
from pathlib import Path

HOST = "127.0.0.1"
PORT = 5050
BUFFER_SIZE = 4096
MAX_FILE_SIZE = 150 * 1024
DOWNLOAD_DIR = Path("downloads")

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
            message = json.dumps(data).encode("utf-8")
            msg_length = len(message)
            # Match the server's 64-byte fixed padding schema
            send_length = str(msg_length).encode("utf-8")
            send_length += b" " * (64 - len(send_length))

            sock.sendall(send_length)
            sock.sendall(message)
        except Exception as e:
            print(f"\nError sending message: {e}")
            running = False


def receive_loop(sock):
    """Background thread that continuously reads formatted packets from the server."""
    global running
    while running:
        try:
            # Read the 64-byte length prefix
            header = sock.recv(64)
            if not header:
                print("\nConnection closed by server.")
                break

            msg_length = int(header.decode("utf-8").strip())

            # Read the full payload body based on the header size
            chunks = []
            bytes_received = 0
            while bytes_received < msg_length:
                chunk = sock.recv(min(msg_length - bytes_received, BUFFER_SIZE))
                if not chunk:
                    raise ConnectionError("Incomplete message payload received.")
                chunks.append(chunk)
                bytes_received += len(chunk)

            payload = b"".join(chunks).decode("utf-8")
            message = json.loads(payload)

            # Handle standard messages vs file downloads
            if "file" in message:
                handle_incoming_file(message["file"])
            else:
                print_message(message)

        except Exception as e:
            if running:
                print(f"\nError receiving data: {e}")
            break
    running = False


### Client Logic and Command Handling ###


def connect_and_register(host, port):
    """Establishes connection and transmits initial username packet."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    username = input("Enter your username: ").strip()

    # Matched to server syntax: register_client looks for "username" directly in root
    send_json(sock, {"username": username})
    return sock


def send_upload(sock, file_path):
    """Reads a local file, confirms size compliance, and uploads as a hex payload."""
    if not file_path.is_file():
        print(f"File not found: {file_path}")
        return
    if file_path.stat().st_size > MAX_FILE_SIZE:
        print(f"File is too large (max {MAX_FILE_SIZE} bytes).")
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
        print(f"Uploading {file_path.name}... waiting for server verification.")
    except Exception as e:
        print(f"Error processing file for upload: {e}")


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
        print(
            f"{prefix}[SYSTEM] File downloaded successfully and saved to: {target_path}"
        )
    except Exception as e:
        print(f"{prefix}[ERROR] Failed to save downloaded file: {e}")

    # Redraw a clean prompt for the main input thread seamlessly
    print("> ", end="", flush=True)


def print_message(message):
    """Parses structural JSON payloads and uses ANSI sequences to prevent prompt collisions."""
    prefix = "\r\033[K"

    if "system" in message:
        print(f"{prefix}[SYSTEM] {message.get('message', '')}")
    elif "error" in message:
        print(f"{prefix}[ERROR] {message.get('error', '')}")
    elif "chat" in message:
        chat_data = message["chat"]
        print(f"{prefix}[{chat_data.get('from')}]: {chat_data.get('message', '')}")
    elif "private_message" in message:
        pm_data = message["private_message"]
        print(f"{prefix}[PM from {pm_data.get('from')}]: {pm_data.get('message', '')}")
    elif "users" in message:
        print(f"{prefix}[ACTIVE USERS] {', '.join(message['users'])}")
    elif "files" in message:
        print(
            f"{prefix}[SERVER FILES] {', '.join(message['files']) if message['files'] else 'No files found.'}"
        )
    elif "message" in message:
        print(f"{prefix}[SERVER] {message.get('message', '')}")
    else:
        print(f"{prefix}[RAW DATA] {message}")

    # Keep the prompt cleanly pinned to the very bottom of the window
    print("> ", end="", flush=True)


def print_help():
    print(
        "\n=================== COMMAND MENU ===================\n"
        "  /help                           Display menu options\n"
        "  /quit                           Disconnect safely from server\n"
        "  /users                          List all online usernames\n"
        "  /pm <username> <message>        Send a private message\n"
        "  /rps <username>                 Challenge an online player to RPS\n"
        "  /files                          List files hosted on the server\n"
        "  /upload <filepath>              Upload a local file (< 150KB)\n"
        "  /download <filename>            Download an uploaded server file\n"
        "  \n"
        "  * During an active RPS match, just type: rock, paper, or scissors\n"
        "  * Anything else typed is sent as a public room broadcast.\n"
        "====================================================\n"
    )


def main():
    global running
    host = sys.argv[1] if len(sys.argv) >= 2 else HOST
    port = int(sys.argv[2]) if len(sys.argv) >= 3 else PORT

    try:
        sock = connect_and_register(host, port)
    except Exception as exc:
        print(f"Could not connect to or register with {host}:{port}: {exc}")
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
        print("\nClosing connection manually.")
    finally:
        running = False
        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()
