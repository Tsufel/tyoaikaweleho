"""HTTPS for the update and DLC downloads.

Python checks certificates only against the roots already in the Windows
certificate store. Windows fills that store on demand, when a program
using Windows' own TLS needs a root, so on some PCs the root GitHub's
certificates chain to was never added and every request failed with
CERTIFICATE_VERIFY_FAILED. Trust the Windows store (so roots added by
security software, proxies or the organisation still work) plus certifi's
copy of Mozilla's root list.
"""
import functools
import os
import socket
import ssl
import urllib.error
import urllib.request


@functools.cache
def ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()   # Windows certificate store
    try:
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    except (ImportError, OSError, ssl.SSLError):
        pass   # the store alone is still better than no checks at all
    return ctx


def has_bundled_roots() -> bool:
    """certifi's root list shipped with the app. ssl_context() quietly does
    without it, so the smoke test checks the build didn't drop it."""
    try:
        import certifi
        return os.path.isfile(certifi.where())
    except ImportError:
        return False


def urlopen(req: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())


def is_cert_error(exc: BaseException) -> bool:
    # urlopen wraps it in URLError(reason=SSLCertVerificationError)
    return isinstance(getattr(exc, "reason", exc), ssl.SSLCertVerificationError)


def describe_error(exc: BaseException) -> str:
    """Error text for the user; certificate failures get a plain explanation."""
    if is_cert_error(exc):
        return ("GitHub's security certificate could not be verified, so the "
                "connection was stopped.\n\nAntivirus HTTPS scanning, a network "
                "proxy or a wrong date and time on this PC can cause this.")
    return str(exc)


def classify_error(exc: BaseException) -> str:
    """Sort a failed request into "certificate", "timeout", "offline",
    "http" or "other" so the user is told what went wrong in plain words."""
    if is_cert_error(exc):
        return "certificate"
    if isinstance(exc, urllib.error.HTTPError):
        return "http"
    reason = getattr(exc, "reason", exc) if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, (TimeoutError, socket.timeout)) or (
            isinstance(reason, str) and "timed out" in reason.lower()):
        return "timeout"
    if isinstance(reason, ssl.SSLError):
        return "other"
    # DNS failure (socket.gaierror), refused/reset connections, no network
    if isinstance(reason, OSError):
        return "offline"
    return "other"


def describe_check_failure(exc: BaseException) -> str:
    """Why an update check failed, for the user: never the raw exception
    text, which is technical and can carry addresses or paths."""
    kind = classify_error(exc)
    if kind == "certificate":
        return describe_error(exc)
    if kind == "timeout":
        return ("GitHub took too long to answer. The connection may be slow "
                "or busy — try again in a moment.")
    if kind == "offline":
        return ("GitHub could not be reached. Check that this PC is connected "
                "to the internet, then try again.")
    if kind == "http":
        code = getattr(exc, "code", None)
        if code in (403, 429):
            return ("GitHub is limiting requests right now (too many checks). "
                    "Try again in an hour.")
        if isinstance(code, int) and code >= 500:
            return (f"GitHub had a problem answering (error {code}). "
                    "Try again later.")
        return f"GitHub turned the request down (error {code}). Try again later."
    return "Something went wrong while talking to GitHub. Try again later."
