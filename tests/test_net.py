"""services.net: update/DLC HTTPS trusts certifi's roots on top of the
Windows store, so a root missing from the store no longer fails every
request with CERTIFICATE_VERIFY_FAILED. Uses a loopback TLS server whose
test root (tests/fixtures/tls) is in neither list unless a test adds it."""
import http.server
import os
import ssl
import sys
import threading
import urllib.error
import urllib.request

import certifi
import pytest

from services import net

TLS = os.path.join(os.path.dirname(__file__), "fixtures", "tls")
TEST_ROOT = os.path.join(TLS, "ca.pem")


@pytest.fixture(autouse=True)
def fresh_context():
    net.ssl_context.cache_clear()
    yield
    net.ssl_context.cache_clear()


@pytest.fixture()
def https_url():
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(TLS, "localhost.pem"), os.path.join(TLS, "localhost.key"))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"https://localhost:{srv.server_address[1]}/"
    srv.shutdown()
    srv.server_close()


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Tyoaikaweleho"})
    with net.urlopen(req, 5) as r:
        return r.read()


def test_unknown_root_is_a_cert_error(https_url):
    with pytest.raises(urllib.error.URLError) as info:
        _get(https_url)
    assert net.is_cert_error(info.value)
    assert "certificate could not be verified" in net.describe_error(info.value)


def test_roots_from_certifi_are_trusted(https_url, monkeypatch):
    # the reported failure: the root is not in the Windows store, but it is
    # in the bundled list
    monkeypatch.setattr(certifi, "where", lambda: TEST_ROOT)
    assert _get(https_url) == b"ok"


def test_context_verifies_and_keeps_the_windows_store(monkeypatch):
    monkeypatch.setattr(certifi, "where", lambda: TEST_ROOT)
    ctx = net.ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    subjects = [dict(x[0] for x in c["subject"]).get("commonName") for c in ctx.get_ca_certs()]
    assert "Tyoaikaweleho Test Root CA" in subjects
    if sys.platform == "win32":
        assert len(subjects) > 1   # store roots loaded too, not replaced


def test_real_certifi_bundle_is_loaded():
    n_default = ssl.create_default_context().cert_store_stats()["x509_ca"]
    assert net.ssl_context().cert_store_stats()["x509_ca"] > n_default


def test_missing_certifi_falls_back_to_the_store(monkeypatch):
    monkeypatch.setitem(sys.modules, "certifi", None)   # import raises ImportError
    ctx = net.ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_unreadable_bundle_falls_back_to_the_store(monkeypatch, tmp_path):
    monkeypatch.setattr(certifi, "where", lambda: str(tmp_path / "missing.pem"))
    assert net.ssl_context().verify_mode == ssl.CERT_REQUIRED


def test_has_bundled_roots(monkeypatch, tmp_path):
    assert net.has_bundled_roots()
    monkeypatch.setattr(certifi, "where", lambda: str(tmp_path / "missing.pem"))
    assert not net.has_bundled_roots()
    monkeypatch.setitem(sys.modules, "certifi", None)
    assert not net.has_bundled_roots()


def test_urlopen_passes_the_shared_context(monkeypatch):
    seen = {}

    def fake(req, timeout=None, context=None):
        seen.update(timeout=timeout, context=context)
        return "resp"

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert net.urlopen(urllib.request.Request("https://example.invalid/"), 7) == "resp"
    assert seen == {"timeout": 7, "context": net.ssl_context()}


@pytest.mark.parametrize("exc, friendly", [
    (urllib.error.URLError(ssl.SSLCertVerificationError(1, "unable to get local issuer certificate")), True),
    (ssl.SSLCertVerificationError(1, "certificate has expired"), True),
    (urllib.error.URLError(ConnectionRefusedError(10061, "refused")), False),
    (urllib.error.URLError("timed out"), False),
    (ssl.SSLError(1, "wrong version number"), False),
])
def test_describe_error(exc, friendly):
    text = net.describe_error(exc)
    assert ("certificate could not be verified" in text) is friendly
    if not friendly:
        assert text == str(exc)
