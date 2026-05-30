import socket
import threading


HOST = "127.0.0.1"
PORT = 5000
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


def start_client() -> None:
    nickname = input("Nickname: ").strip()
    if not nickname:
        print("Nickname cannot be empty.")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))

        receiver = threading.Thread(
            target=receive_messages,
            args=(client_socket,),
            daemon=True,
        )
        receiver.start()

        client_socket.sendall(nickname.encode(ENCODING))

        print("Connected to chat server.")
        print("Commands: /users, /quit")

        while True:
            try:
                message = input()
            except EOFError:
                message = "/quit"

            client_socket.sendall(message.encode(ENCODING))

            if message.strip() == "/quit":
                break


if __name__ == "__main__":
    start_client()
