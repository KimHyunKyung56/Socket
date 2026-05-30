import socket
import threading
from datetime import datetime
from pathlib import Path


HOST = "127.0.0.1"
PORT = 5000
BUFFER_SIZE = 1024
ENCODING = "utf-8"
LOG_FILE = Path("server.log")


class ChatServer:
    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host = host
        self.port = port
        self.clients: dict[socket.socket, str] = {}
        self.clients_lock = threading.Lock()

    def log_event(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)

        with LOG_FILE.open("a", encoding=ENCODING) as log_file:
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

    def register_client(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
    ) -> str | None:
        self.send_message(client_socket, "Enter your nickname:")

        try:
            nickname_data = client_socket.recv(BUFFER_SIZE)
        except OSError:
            return None

        if not nickname_data:
            return None

        nickname = nickname_data.decode(ENCODING).strip()
        if not nickname:
            self.send_message(client_socket, "[System] Empty nickname is not allowed.")
            return None

        with self.clients_lock:
            if nickname in self.clients.values():
                self.send_message(client_socket, "[System] Nickname already in use.")
                return None

            self.clients[client_socket] = nickname

        self.log_event(f"{nickname} connected from {address[0]}:{address[1]}")
        self.send_message(client_socket, f"[System] Welcome, {nickname}!")
        self.send_message(client_socket, "[System] Commands: /users, /quit")
        self.broadcast(f"[System] {nickname} joined the chat.", exclude=client_socket)
        return nickname

    def handle_client(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
    ) -> None:
        with client_socket:
            nickname = self.register_client(client_socket, address)
            if nickname is None:
                return

            while True:
                try:
                    data = client_socket.recv(BUFFER_SIZE)
                except ConnectionResetError:
                    break

                if not data:
                    break

                message = data.decode(ENCODING).strip()
                if not message:
                    continue

                if message == "/quit":
                    self.send_message(client_socket, "[System] Disconnecting...")
                    break

                if message == "/users":
                    self.send_message(
                        client_socket,
                        f"[System] Connected users: {self.list_users()}",
                    )
                    continue

                chat_message = f"[{nickname}] {message}"
                self.log_event(chat_message)
                self.broadcast(chat_message)

        self.remove_client(client_socket)

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()

            self.log_event(f"TCP chat server started on {self.host}:{self.port}")

            while True:
                client_socket, address = server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                thread.start()


def main() -> None:
    server = ChatServer()
    server.serve_forever()


if __name__ == "__main__":
    main()
