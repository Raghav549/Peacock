import http.client
import io
import socket
import threading
import time
import unittest

from peacock.compiler.diagnostics import CapabilityError
from peacock.platforms.httpd import BoundedHTTPServer, MAX_BODY_BYTES, MAX_HEADER_BYTES, ServerError
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM
from tests.support import compile_ok, run_source


SOURCE = """
उपयोग सेवक
कार्य मुख्य() -> एकक {
    अधिकार सञ्जाल;
    स्थापय स = सेवक.श्रृणु("127.0.0.1", ०);
    मुद्रय(सेवक.द्वार(स));
    स्थापय निवेदन = सेवक.स्वीकुरु(स, ५०००);
    निश्चिनु दैर्घ्य(निवेदन) == ५;
    निश्चिनु निवेदन[१] == "POST";
    निश्चिनु निवेदन[२] == "/sutra?x=1";
    निश्चिनु निवेदन[४] == "सूत्र";
    सेवक.प्रत्युत्तरय(स, निवेदन[०], २०१, "प्राप्तम्: " + निवेदन[४]);
    सेवक.पिदध्मि(स);
    मुद्रय("server closed");
}
"""


class HTTPServerUnitTests(unittest.TestCase):
    def test_timeout_validation_and_idempotent_close(self):
        server = BoundedHTTPServer("localhost", 0)
        self.assertGreater(server.port, 0)
        self.assertIsNone(server.accept(0))
        self.assertIsNone(server.accept(1))
        with self.assertRaisesRegex(ServerError, "timeout"):
            server.accept(60_001)
        server.close()
        server.close()
        with self.assertRaisesRegex(ServerError, "closed"):
            server.accept(0)
        with self.assertRaisesRegex(ServerError, "numeric IP"):
            BoundedHTTPServer("example.com", 0)

    def test_request_framing_utf8_and_size_limits(self):
        cases = [
            (b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n", "transfer-encoding"),
            (f"POST / HTTP/1.1\r\nContent-Length: {MAX_BODY_BYTES + 1}\r\n\r\n".encode(), "body length"),
            (b"POST / HTTP/1.1\r\nContent-Length: +1\r\n\r\nx", "content-length"),
            (b"POST / HTTP/1.1\r\nContent-Length: 1\r\n\r\n\xff", "UTF-8"),
            (b"GET / HTTP/1.1\r\nX-Large: " + b"a" * (MAX_HEADER_BYTES + 1) + b"\r\n\r\n", "headers exceed"),
        ]
        for request, message in cases:
            with self.subTest(message=message):
                server = BoundedHTTPServer("127.0.0.1", 0)
                client = socket.create_connection(server.socket.getsockname(), timeout=2)
                try:
                    client.sendall(request)
                    with self.assertRaisesRegex(ServerError, message):
                        server.accept(1000)
                    self.assertIsNone(server.pending)
                finally:
                    client.close()
                    server.close()

    def test_response_validation_preserves_request_for_valid_retry(self):
        server = BoundedHTTPServer("127.0.0.1", 0)
        client = socket.create_connection(server.socket.getsockname(), timeout=2)
        try:
            client.sendall(b"POST / HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
            request = server.accept(1000)
            self.assertIsNotNone(request)
            with self.assertRaisesRegex(ServerError, "status"):
                server.respond(request[0], 199, "bad")
            with self.assertRaisesRegex(ServerError, "response body"):
                server.respond(request[0], 200, "x" * (MAX_BODY_BYTES + 1))
            with self.assertRaisesRegex(ServerError, "content-type"):
                server.respond(request[0], 200, "bad", "text/plain\r\nX-Evil: yes")
            self.assertIsNotNone(server.pending)
            server.respond(request[0], 200, "ठीक")
            received = bytearray()
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)
            self.assertIn(b"HTTP/1.1 200 OK", received)
            self.assertTrue(received.endswith("ठीक".encode("utf-8")))
            self.assertIsNone(server.pending)
        finally:
            client.close()
            server.close()


class NativeHTTPServerTests(unittest.TestCase):
    def test_real_request_is_handled_by_peacock_program(self):
        image = compile_ok(SOURCE).image
        output = io.StringIO()
        host = HostPolicy(grants=frozenset({"network"}))
        vm = VM(image, host, stdout=output)
        errors = []

        def run():
            try:
                vm.run()
            except BaseException as exc:  # surfaced in the main test thread
                errors.append(exc)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        connection = None
        try:
            deadline = time.monotonic() + 3
            while not output.getvalue() and time.monotonic() < deadline and not errors:
                time.sleep(0.01)
            self.assertFalse(errors, errors)
            port = int(output.getvalue().splitlines()[0])
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
            connection.request("POST", "/sutra?x=1", body="सूत्र".encode("utf-8"), headers={"Content-Type": "text/plain; charset=utf-8", "X-Test": "yes"})
            response = connection.getresponse()
            payload = response.read().decode("utf-8")
            self.assertEqual(response.status, 201)
            self.assertEqual(payload, "प्राप्तम्: सूत्र")
            self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
            thread.join(4)
            self.assertFalse(thread.is_alive(), "PEACOCK server VM did not finish")
            self.assertFalse(errors, errors)
            self.assertIn("server closed", output.getvalue())
            self.assertEqual(host.server_handles, {})
        finally:
            if connection is not None:
                connection.close()
            if thread.is_alive():
                host.close()
                thread.join(2)
            host.close()

    def test_network_capability_is_required(self):
        with self.assertRaises(CapabilityError):
            run_source(SOURCE)


if __name__ == "__main__":
    unittest.main()
