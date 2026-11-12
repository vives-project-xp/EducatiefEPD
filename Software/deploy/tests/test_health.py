"""Exercise HTTP health semantics against a local server, without Django or Docker."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
from pathlib import Path
import threading
import unittest
import urllib.error
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("epd_health", Path(__file__).parents[2] / "healthcheck.py")
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)
SPEC = importlib.util.spec_from_file_location("epd_deploy", Path(__file__).parents[1] / "deploy.py")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


class Handler(BaseHTTPRequestHandler):
    status = 200
    body = b'{"status":"ok"}'
    requests = []

    def do_GET(self):
        type(self).requests.append((self.path, self.headers.get("Host"),
                                    self.headers.get("X-Forwarded-Proto")))
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        if type(self).status == 302:
            self.send_header("Location", "/login")
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *args):
        pass


class HealthTests(unittest.TestCase):
    def setUp(self):
        Handler.status, Handler.body, Handler.requests = 200, b'{"status":"ok"}', []
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/health/"
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_internal_check_sends_configured_host_and_proxy_scheme(self):
        health.check("epd.example", self.url)
        self.assertEqual(Handler.requests, [("/health/", "epd.example", "https")])

    def test_internal_check_rejects_redirect_errors_and_wrong_json(self):
        for status, body in [(302, b'{"status":"ok"}'), (503, b'{"status":"unavailable"}'),
                             (200, b'{"status":"wrong"}'), (200, b'<html>Login</html>')]:
            with self.subTest(status=status, body=body):
                Handler.status, Handler.body = status, body
                with self.assertRaises((urllib.error.HTTPError, RuntimeError, ValueError)):
                    health.check("epd.example", self.url)
        self.assertFalse(any(path == "/login" for path, _, _ in Handler.requests))

    def test_external_health_requires_exact_success(self):
        runner = object.__new__(deploy.Deployer)
        runner.config = {"health_url": self.url}
        runner.external_health()
        for status, body in [(302, b'{"status":"ok"}'), (503, b'{}'), (200, b'{}')]:
            Handler.status, Handler.body = status, body
            with self.subTest(status=status), patch.object(deploy.time, "sleep"):
                with self.assertRaises(deploy.DeploymentError):
                    runner.external_health()
        self.assertFalse(any(path == "/login" for path, _, _ in Handler.requests))


if __name__ == "__main__":
    unittest.main()
