import argparse
import io
import socket
import threading
from datetime import datetime
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
DEFAULT_BACKLOG = 5
DEFAULT_MAX_CLIENTS = 10
DEFAULT_MAX_MESSAGE_LENGTH = 500
MAX_NICKNAME_LENGTH = 20
ENCODING = "utf-8"
DEFAULT_LOG_FILE = Path("server.log")

COMMAND_HELP = """[System] Commands:
  /help                 Show command list
  /users                Show connected users
  /msg <nickname> <msg> Send a private message
  /quit                 Leave the chat"""


class ChatServer:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        log_file: Path = DEFAULT_LOG_FILE,
        backlog: int = DEFAULT_BACKLOG,
        max_clients: int = DEFAULT_MAX_CLIENTS,
        max_message_length: int = DEFAULT_MAX_MESSAGE_LENGTH,
    ) -> None:
        self.host = host
        self.port = port
        self.log_file = log_file
        self.backlog = backlog
        self.max_clients = max_clients
        self.max_message_length = max_message_length
        self.clients: dict[socket.socket, str] = {}
        self.clients_lock = threading.Lock()

    def log_event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)

        with self.log_file.open("a", encoding=ENCODING) as log_file:
            log_file.write(formatted + "\n")

    def send_message(self, client_socket: socket.socket, message: str) -> None:
        client_socket.sendall((message + "\n").encode(ENCODING))

    def broadcast(
        self,
        message: str,
        exclude: socket.socket | None = None,
    ) -> None:
        disconnected_clients: list[socket.socket] = []

        with self.clients_lock:
            current_clients = list(self.clients.keys())

        for client_socket in current_clients:
            if client_socket is exclude:
                continue

            try:
                self.send_message(client_socket, message)
            except OSError:
                disconnected_clients.append(client_socket)

        for client_socket in disconnected_clients:
            self.remove_client(client_socket)

    def remove_client(self, client_socket: socket.socket) -> None:
        with self.clients_lock:
            nickname = self.clients.pop(client_socket, None)

        if nickname:
            self.log_event(f"{nickname} disconnected")
            self.broadcast(f"[System] {nickname} left the chat.", exclude=client_socket)

        try:
            client_socket.close()
        except OSError:
            pass

    def list_users(self) -> str:
        with self.clients_lock:
            nicknames = sorted(self.clients.values())

        if not nicknames:
            return "No connected users"

        return ", ".join(nicknames)

    def client_count(self) -> int:
        with self.clients_lock:
            return len(self.clients)

    def find_client_by_nickname(self, nickname: str) -> socket.socket | None:
        with self.clients_lock:
            for client_socket, current_nickname in self.clients.items():
                if current_nickname == nickname:
                    return client_socket

        return None

    def register_client(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
        reader: io.TextIOWrapper,
    ) -> str | None:
        self.send_message(client_socket, "Enter your nickname:")

        try:
            nickname_data = reader.readline()
        except OSError:
            return None

        if not nickname_data:
            return None

        nickname = nickname_data.strip()
        if not nickname:
            self.send_message(client_socket, "[System] Empty nickname is not allowed.")
            return None

        if len(nickname) > MAX_NICKNAME_LENGTH:
            self.send_message(
                client_socket,
                f"[System] Nickname must be {MAX_NICKNAME_LENGTH} characters or less.",
            )
            return None

        if nickname.startswith("/"):
            self.send_message(client_socket, "[System] Nickname cannot start with '/'.")
            return None

        with self.clients_lock:
            if len(self.clients) >= self.max_clients:
                self.send_message(client_socket, "[System] Server is full. Try again later.")
                return None

            if nickname in self.clients.values():
                self.send_message(client_socket, "[System] Nickname already in use.")
                return None

            self.clients[client_socket] = nickname

        self.log_event(f"{nickname} connected from {address[0]}:{address[1]}")
        self.send_message(client_socket, f"[System] Welcome, {nickname}!")
        self.send_message(client_socket, COMMAND_HELP)
        self.broadcast(f"[System] {nickname} joined the chat.", exclude=client_socket)
        return nickname

    def handle_command(
        self,
        client_socket: socket.socket,
        nickname: str,
        message: str,
    ) -> bool:
        command, _, arguments = message.partition(" ")

        if command == "/quit":
            self.send_message(client_socket, "[System] Disconnecting...")
            return False

        if command == "/help":
            self.send_message(client_socket, COMMAND_HELP)
            return True

        if command == "/users":
            self.send_message(
                client_socket,
                f"[System] Connected users: {self.list_users()}",
            )
            return True

        if command == "/msg":
            self.send_private_message(client_socket, nickname, arguments)
            return True

        self.send_message(client_socket, f"[System] Unknown command: {command}")
        self.send_message(client_socket, "[System] Type /help to see available commands.")
        return True

    def discard_remaining_line(self, reader: io.TextIOWrapper) -> None:
        while True:
            chunk = reader.readline(1024)
            if not chunk or chunk.endswith("\n") or len(chunk) < 1024:
                return

    def send_private_message(
        self,
        sender_socket: socket.socket,
        sender_nickname: str,
        arguments: str,
    ) -> None:
        target_nickname, _, private_message = arguments.partition(" ")
        if not target_nickname or not private_message:
            self.send_message(
                sender_socket,
                "[System] Usage: /msg <nickname> <message>",
            )
            return

        target_socket = self.find_client_by_nickname(target_nickname)
        if target_socket is None:
            self.send_message(sender_socket, f"[System] User not found: {target_nickname}")
            return

        if target_socket is sender_socket:
            self.send_message(sender_socket, "[System] You cannot send a private message to yourself.")
            return

        if len(private_message) > self.max_message_length:
            self.send_message(
                sender_socket,
                f"[System] Private message must be {self.max_message_length} characters or less.",
            )
            return

        formatted_for_target = f"[Private from {sender_nickname}] {private_message}"
        formatted_for_sender = f"[Private to {target_nickname}] {private_message}"

        try:
            self.send_message(target_socket, formatted_for_target)
            self.send_message(sender_socket, formatted_for_sender)
        except OSError:
            self.remove_client(target_socket)
            self.send_message(sender_socket, f"[System] User disconnected: {target_nickname}")
            return

        self.log_event(f"[Private] {sender_nickname} -> {target_nickname}: {private_message}")

    def handle_client(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
    ) -> None:
        with client_socket:
            reader = client_socket.makefile("r", encoding=ENCODING)

            nickname = self.register_client(client_socket, address, reader)
            if nickname is None:
                reader.close()
                return

            try:
                while True:
                    try:
                        line = reader.readline(self.max_message_length + 2)
                    except (ConnectionResetError, OSError):
                        break

                    if not line:
                        break

                    if len(line) > self.max_message_length + 1:
                        if not line.endswith("\n"):
                            self.discard_remaining_line(reader)
                        self.send_message(
                            client_socket,
                            f"[System] Message must be {self.max_message_length} characters or less.",
                        )
                        continue

                    message = line.strip()
                    if not message:
                        continue

                    if message.startswith("/"):
                        should_continue = self.handle_command(
                            client_socket,
                            nickname,
                            message,
                        )
                        if not should_continue:
                            break
                        continue

                    chat_message = f"[{nickname}] {message}"
                    self.log_event(chat_message)
                    self.broadcast(chat_message)
            finally:
                reader.close()

        self.remove_client(client_socket)

    def shutdown(self) -> None:
        with self.clients_lock:
            current_clients = list(self.clients.keys())
            self.clients.clear()

        for client_socket in current_clients:
            try:
                self.send_message(client_socket, "[System] Server is shutting down.")
                client_socket.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind((self.host, self.port))
                server_socket.listen(self.backlog)

                self.log_event(
                    "TCP chat server started on "
                    f"{self.host}:{self.port} "
                    f"(backlog={self.backlog}, max_clients={self.max_clients})"
                )

                while True:
                    client_socket, address = server_socket.accept()
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True,
                    )
                    thread.start()
        except KeyboardInterrupt:
            self.log_event("Server interrupted by user.")
        finally:
            self.shutdown()
            self.log_event("TCP chat server stopped.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TCP chat server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server host to bind.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Server port.")
    parser.add_argument(
        "--backlog",
        default=DEFAULT_BACKLOG,
        type=int,
        help="Maximum queued connection requests for listen().",
    )
    parser.add_argument(
        "--max-clients",
        default=DEFAULT_MAX_CLIENTS,
        type=int,
        help="Maximum number of connected clients.",
    )
    parser.add_argument(
        "--max-message-length",
        default=DEFAULT_MAX_MESSAGE_LENGTH,
        type=int,
        help="Maximum length of one chat message.",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        type=Path,
        help="Path to the server log file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ChatServer(
        host=args.host,
        port=args.port,
        log_file=args.log_file,
        backlog=args.backlog,
        max_clients=args.max_clients,
        max_message_length=args.max_message_length,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
