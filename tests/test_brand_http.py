from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from codex_ads.creative import _fetch_html, extract_brand_dna


@pytest.fixture
def html_server():
    response = {"body": b"", "content_type": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if response["content_type"] is not None:
                self.send_header("Content-Type", response["content_type"])
            self.end_headers()
            self.wfile.write(response["body"])

        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield response, f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.mark.parametrize(
    ("encoding", "content_type"),
    [
        ("iso-8859-1", "text/html; charset=iso-8859-1"),
        ("cp1252", 'text/html; charset="Windows-1252"'),
        ("utf-8", "text/html; charset=UTF-8"),
        ("utf-8", "text/html"),
        ("utf-8", None),
        ("utf-8", "text/html; charset=unknown-encoding"),
        ("utf-8", "text/html; charset=base64"),
    ],
)
def test_brand_fetch_preserves_text_in_response_charset(html_server, encoding, content_type):
    response, url = html_server
    html = '<title>Café Crème</title><meta name="description" content="Crème fraîche">'
    response.update(body=html.encode(encoding), content_type=content_type)

    assert _fetch_html(url) == html
    profile = extract_brand_dna(url)
    assert profile["brand_name"] == "Café Crème"
    assert profile["description"] == "Crème fraîche"


def test_windows_charset_preserves_typographic_punctuation(html_server):
    response, url = html_server
    html = "<title>Crème’s café — opening soon</title>"
    response.update(body=html.encode("cp1252"), content_type="text/html; charset=windows-1252")

    assert extract_brand_dna(url)["brand_name"] == "Crème’s café — opening soon"


@pytest.mark.parametrize("charset", ["utf-8", "unknown-encoding"])
def test_brand_fetch_keeps_existing_malformed_byte_handling(html_server, charset):
    response, url = html_server
    response.update(body=b"<title>Caf\xc3\xa9\xff</title>", content_type=f"text/html; charset={charset}")

    assert extract_brand_dna(url)["brand_name"] == "Café"


def test_dna_cli_writes_profile_using_http_charset(html_server, tmp_path):
    response, url = html_server
    response.update(
        body="<title>Crème’s café</title>".encode("cp1252"),
        content_type="text/html; charset=windows-1252",
    )
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "dna", "--url", url, "--output-dir", str(tmp_path)],
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    profile = json.loads((tmp_path / "brand-profile.json").read_text())
    assert profile["brand_name"] == "Crème’s café"
