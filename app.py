"""
app.py
A simple python http server.
@author Josh Trujillo
"""

import mimetypes
import os
from os.path import abspath
import socket
import typing
import io

from headers import Headers
from request import Request

SERVER_ROOT = os.path.abspath("www")

FILE_RESPONSE_TEMPLATE = """\
HTTP/1.1 200 OK
Content-type: {content_type}
Content-length: {content_length}

""".replace(
    "\n", "\r\n"
)


class Response:
    """
    An HTTP response.

    Parameters:
        status: The response status line. e.g., "200 OK".
        headers: The response headers.
        body: A file containing the response body.
        content: A string representing the response body. If this is
            provided, then body is ignored.
        encoding: An encoding for the content, if provided.
    """

    def __init__(
        self,
        status: str,
        headers: typing.Optional[Headers] = None,
        body: typing.Optional[typing.IO] = None,
        content: typing.Optional[str] = None,
        encoding: str = "utf 8",
    ) -> None:

        self.status = status.encode()
        self.headers = headers or Headers()

        if content is not None:
            self.body = io.BytesIO(content.encode(encoding))
        elif body is None:
            self.body = io.BytesIO()
        else:
            self.body = body

    def send(self, sock: socket.socket) -> None:
        """
        Write this response to a socket.
        """
        content_length = self.headers.get("content-length")
        if content_length is None:
            try:
                body_stat = os.fstat(self.body.fileno())
                content_length = body_stat.st_size
            except OSError:
                self.body.seek(0, os.SEEK_END)
                content_length = self.body.tell()
                self.body.seek(0, os.SEEK_SET)

            if content_length > 0:
                self.headers.add("content-length", content_length)

        headers = b"HTTP/1.1 " + self.status + b"\r\n"
        for header_name, header_value in self.headers:
            headers += f"{header_name}: {header_value}\r\n".encode()

        sock.sendall(headers + b"\r\n")
        if content_length > 0:
            sock.sendfile(self.body)


def serve_file(sock: socket.socket, path: str) -> None:
    """
    Given a socket and the relative path to a file (relative to
    SERVER_SOCK), send that file to the socket if it exists.
    If the file doesn't exist, sent a "404 Not Found" response.
    """
    if path == "/":
        path = "/index.html"

    abspath = os.path.normpath(os.path.join(SERVER_ROOT, path.lstrip("/")))
    if not abspath.startswith(SERVER_ROOT):
        response = Response(status="404 Not Found", content="Not Found")
        response.send(sock)
        return

    try:
        with open(abspath, "rb") as f:
            stat = os.fstat(f.fileno())
            content_type, encoding = mimetypes.guess_type(abspath)
            if content_type is None:
                content_type = "application/octet-stream"

            if encoding is not None:
                content_type += f"; charset={encoding}"

            response = Response(status="200 OK", body=f)
            response.headers.add("content-type", content_type)
            response.send(sock)
            return
    except FileNotFoundError:
        response = Response(status="404 Not Found", content="Not Found")
        response.send(sock)
        return


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

METHOD_NOT_ALLOWED_RESPONSE = b"""\
HTTP/1.1 405 Method Not Allowed
Content-type: text/plain
Content-length: 17

Method Not Allowed""".replace(
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
                if "100-continue" in request.headers.get("expect", ""):
                    response = Response(status="100 Continue")
                    response.send(client_sock)

                try:
                    content_length = int(request.headers.get("content-length", "0"))
                except ValueError:
                    content_length = 0

                if content_length:
                    body = request.body.read(content_length)
                    print("Request Body", body)

                if request.method != "GET":
                    response = Response(
                        status="405 Method Not Allowed", content="Method Not Allowed"
                    )
                    response.send(client_sock)
                    continue

                serve_file(client_sock, request.path)
            except Exception as e:
                print(f"Failed to parse request: {e}")
                response = Response(status="400 Bad Request", content="Bad Request")
                response.send(client_sock)
