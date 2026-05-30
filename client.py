import argparse
import socket
import threading


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
BUFFER_SIZE = 1024
ENCODING = "utf-8"


def receive_messages(client_socket: socket.socket) -> None:
    while True:
        try:
            data = client_socket.recv(BUFFER_SIZE)
        except OSError:
            break

        if not data:
            print("Server connection closed.")
            break

        print(data.decode(ENCODING).strip())


def send_message(client_socket: socket.socket, message: str) -> None:
    client_socket.sendall((message + "\n").encode(ENCODING))


def start_client(host: str, port: int, nickname: str | None = None) -> None:
    if nickname is None:
        nickname = input("Nickname: ").strip()

    if not nickname:
        print("Nickname cannot be empty.")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        try:
            client_socket.connect((host, port))
        except ConnectionRefusedError:
            print(f"Could not connect to server at {host}:{port}.")
            return

        receiver = threading.Thread(
            target=receive_messages,
            args=(client_socket,),
            daemon=True,
        )
        receiver.start()

        send_message(client_socket, nickname)

        print(f"Connected to chat server at {host}:{port}.")
        print("Commands: /help, /users, /msg <nickname> <message>, /quit")

        while True:
            try:
                message = input()
            except EOFError:
                message = "/quit"

            try:
                send_message(client_socket, message)
            except OSError:
                print("Server connection lost.")
                break

            if message.strip() == "/quit":
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TCP chat client.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server host.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Server port.")
    parser.add_argument("--nickname", help="Nickname to use after connecting.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_client(args.host, args.port, args.nickname)


if __name__ == "__main__":
    main()
