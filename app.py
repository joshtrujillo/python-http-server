"""
app.py
A simple python http server.
@author Josh Trujillo
"""

import socket
import typing


class Request(typing.NamedTuple):
    method: str
    path: str
    headers: typing.Mapping[str, str]

    @classmethod
    def from_socket(cls, sock: socket.socket) -> "Request":
        """
        Read and parse the request from a socket object.

        Raises:
            ValueError: When the request cannot be parsed.
        """
        lines = iter_lines(sock)

        try:
            request_line = next(lines).decode("ascii")
        except StopIteration:
            raise ValueError("Request line missing.")

        try:
            method, path, _ = request_line.split(" ")
        except ValueError:
            raise ValueError(f"Malformed request line {request_line!r}.")

        headers = {}
        for line in lines:
            try:
                name, _, value = line.decode("ascii").partition(":")
                headers[name.lower()] = value.lstrip()
            except ValueError:
                raise ValueError(f"Malformed header line {line!r}.")

        return cls(method=method.upper(), path=path, headers=headers)


def iter_lines(
    sock: socket.socket, bufsize: int = 16_384
) -> typing.Generator[bytes, None, bytes]:
    """
    Given a socket, read all the individual CRLF-separated lines
    and yield each one until an empty one is found. Returns the
    remainder after the empty line.
    """
    buff = b""
    while True:
        data = sock.recv(bufsize)
        if not data:
            return b""

        buff += data
        while True:
            try:
                i = buff.index(b"\r\n")
                line, buff = buff[:i], buff[i + 2 :]
                if not line:
                    return buff

                yield line
            except IndexError:
                break


HOST = "127.0.0.1"
PORT = 9000

RESPONSE = b"""\
HTTP/1.1 200 OK
Content-type: text/html
Content-length: 15

<h1>Hello!</h1>""".replace(
    b"\n", b"\r\n"
)

BAD_REQUEST_RESPONSE = b"""\
HTTP/1.1 400 Bad Request
Content-type: text/plain
Content-length: 11

Bad Request""".replace(
    b"\n", b"\r\n"
)

NOT_FOUND_RESPONSE = b"""\
HTTP/1.1 404 Not Found
Content-type: text/plain
Content-length: 9

Not Found""".replace(
    b"\n", b"\r\n"
)


with socket.socket() as server_sock:
    # Tell the kernel to reuse sockets that are in 'TIME_WAIT' state.
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Binds socket to address
    server_sock.bind((HOST, PORT))

    # 0 is the number of pending connections the socket may have before
    # new connections are refused. Since this server is going to process
    # one connection at a time, we want to refuse any additional connections
    server_sock.listen(0)
    print(f"Listening on {HOST}:{PORT}...")
    print(f"Visit http://{HOST}:{PORT}/")

    while True:
        # Accept incomming connection
        client_sock, client_addr = server_sock.accept()
        print(f"Received connection from {client_addr}.")
        with client_sock:
            try:
                request = Request.from_socket(client_sock)
                print(request)
                client_sock.sendall(NOT_FOUND_RESPONSE)
            except Exception as e:
                print(f"Failed to parse request: {e}")
                client_sock.sendall(BAD_REQUEST_RESPONSE)
