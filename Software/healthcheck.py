"""Check the actual HTTP/DB endpoint inside the web container, without redirects."""
import json
import os
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(host, url="http://127.0.0.1:8001/health/"):
    # Gunicorn is HTTP behind the TLS proxy. Match Django's existing proxy contract.
    request = urllib.request.Request(
        url,
        headers={"Host": host, "X-Forwarded-Proto": "https"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=10) as response:
        if response.status != 200 or json.load(response) != {"status": "ok"}:
            raise RuntimeError("EPD healthcheck failed")


if __name__ == "__main__":
    check(os.environ["DEPLOY_HEALTH_HOST"])
