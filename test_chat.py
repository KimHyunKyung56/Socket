import socket
import threading
import time
from pathlib import Path

from server import ChatServer


HOST = "127.0.0.1"
ENCODING = "utf-8"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
        test_socket.bind((HOST, 0))
        return test_socket.getsockname()[1]


def read_help(reader) -> None:
    first_line = reader.readline().strip()
    assert first_line == "[System] Commands:"

    for _ in range(4):
        assert reader.readline()


def connect_user(port: int, nickname: str):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, port))
    reader = client_socket.makefile("r", encoding=ENCODING)

    assert reader.readline().strip() == "Enter your nickname:"
    client_socket.sendall((nickname + "\n").encode(ENCODING))
    assert reader.readline().strip() == f"[System] Welcome, {nickname}!"
    read_help(reader)

    return client_socket, reader


def send_line(client_socket: socket.socket, message: str) -> None:
    client_socket.sendall((message + "\n").encode(ENCODING))


def main() -> None:
    port = find_free_port()
    server = ChatServer(
        port=port,
        log_file=Path("test_server.log"),
        max_clients=2,
        max_message_length=20,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)

    alice, alice_reader = connect_user(port, "Alice")
    bob, bob_reader = connect_user(port, "Bob")
    assert alice_reader.readline().strip() == "[System] Bob joined the chat."

    send_line(bob, "/users")
    assert bob_reader.readline().strip() == "[System] Connected users: Alice, Bob"

    send_line(alice, "/msg Bob hello")
    assert bob_reader.readline().strip() == "[Private from Alice] hello"
    assert alice_reader.readline().strip() == "[Private to Bob] hello"

    send_line(alice, "/msg Alice self")
    assert alice_reader.readline().strip() == "[System] You cannot send a private message to yourself."

    send_line(bob, "x" * 21)
    assert bob_reader.readline().strip() == "[System] Message must be 20 characters or less."

    carol = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    carol.connect((HOST, port))
    carol_reader = carol.makefile("r", encoding=ENCODING)
    assert carol_reader.readline().strip() == "Enter your nickname:"
    send_line(carol, "Carol")
    assert carol_reader.readline().strip() == "[System] Server is full. Try again later."

    send_line(alice, "/quit")
    assert alice_reader.readline().strip() == "[System] Disconnecting..."

    alice.close()
    bob.close()
    carol.close()
    server.shutdown()
    print("chat integration test passed")


if __name__ == "__main__":
    main()
