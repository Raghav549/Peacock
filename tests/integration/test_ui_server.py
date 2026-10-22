import io
import json
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from peacock.compiler.diagnostics import CapabilityError, HostError
from peacock.platforms import UIWebBackend
from peacock.runtime.host import HostPolicy
from peacock.runtime.vm import VM
from tests.support import compile_ok, read_example, run_source


def request(url: str, *, data: dict | None = None, content_type: str = "application/json"):
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {"Content-Type": content_type} if body is not None else {}
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=2) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


class InteractiveUIServerTests(unittest.TestCase):
    def test_vm_waits_for_real_http_event_and_republishes(self):
        image = compile_ok(read_example("ui_events.सूत्र")).image
        backend = UIWebBackend(port=0, title="घटना परीक्षण")
        host = HostPolicy(grants=frozenset({"ui"}), ui_presenter=backend.present)
        stdout = io.StringIO()
        vm = VM(image, host, stdout=stdout)
        errors = []

        def execute():
            try:
                vm.run()
            except Exception as exc:  # captured for the main test thread
                errors.append(exc)

        thread = threading.Thread(target=execute, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while backend.server is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNotNone(backend.server, "UI host did not start after दृश्य.प्रदर्शय")
            base = backend.url.rstrip("/")
            status, health = request(base + "/healthz")
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(health)["ok"])
            status, html = request(base + "/")
            self.assertEqual(status, 200)
            self.assertIn("<script>", html)
            self.assertIn("fetch('/event'", html)
            self.assertEqual(request(base + "/event", data={}, content_type="text/plain")[0], 415)
            self.assertEqual(request(base + "/event", data={"kind": "click", "unknown": 1})[0], 400)

            button = next(node for node in backend.ui.nodes.values() if node.kind == "button")
            status, response = request(base + "/event", data={"kind": "click", "node": button.id})
            self.assertEqual(status, 202, response)
            self.assertEqual(json.loads(response)["id"], 1)
            thread.join(10)
            self.assertFalse(thread.is_alive(), "VM did not finish after the HTTP event")
            self.assertEqual(errors, [])
            self.assertEqual(stdout.getvalue(), "UI event: स्पर्श / वृद्धि\n")
            status, fragment = request(base + "/fragment")
            self.assertEqual(status, 200)
            self.assertIn("क्लिक: १", fragment)
            status, manifest = request(base + "/manifest.json")
            self.assertEqual(json.loads(manifest)["presents"], 2)
        finally:
            backend.close()
            thread.join(1)

    def test_present_requires_grant_and_attached_backend(self):
        source = """
        उपयोग रङ्ग
        उपयोग दृश्य
        कार्य मुख्य() -> एकक {
            अधिकार दृश्य;
            स्थापय रचना = दृश्य.सृज("घटना", १०, १०, रङ्ग.षोडशात्("#ffffff"));
            दृश्य.प्रदर्शय(रचना);
        }
        """
        with self.assertRaises(CapabilityError):
            run_source(source)
        with self.assertRaises(HostError) as caught:
            run_source(source, grants=("ui",))
        self.assertEqual(caught.exception.code, "PE4006")
        self.assertIn("--ui-serve", caught.exception.message)


if __name__ == "__main__":
    unittest.main()
