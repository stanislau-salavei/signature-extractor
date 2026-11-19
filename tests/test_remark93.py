"""Remark 93 (2026-11-19): update check diagnostics and no false «no connection».
WARNING in the log with the address, error class, HTTP code and rate-limit reset; the used address at start-up;
a rejected SE_UPDATE_API is reported; quotes / invisible characters are trimmed; HTTP 404 from
releases/latest (no release yet) = up to date.  Real HTTP through a local server, no internet."""
import datetime as dt
import http.server
import json
import logging
import threading
import time

import pytest

from core import updater as U

TEST_API = "https://api.github.com/repos/someone/se-update-test/releases/latest"


# ================================================================== api_url()
@pytest.mark.parametrize("raw", [
    TEST_API, f"  {TEST_API}  ", f'"{TEST_API}"', f"'{TEST_API}'", f"\u201c{TEST_API}\u201d",
    f"\u00ab{TEST_API}\u00bb", f"\ufeff{TEST_API}", f"\u200b{TEST_API}\u200b", f"\u00a0{TEST_API}\r\n",
    f'"{TEST_API}" ',
])
def test_api_url_trims_quotes_and_invisible(monkeypatch, raw):
    monkeypatch.setenv(U.API_ENV, raw)
    assert U.api_url() == TEST_API


def test_api_url_unset_or_blank_is_project_without_warning(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="core.updater")
    monkeypatch.delenv(U.API_ENV, raising=False)
    assert U.api_url() == U.API_LATEST
    monkeypatch.setenv(U.API_ENV, '  ""  ')
    assert U.api_url() == U.API_LATEST
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize("raw", ["api.github.com/repos/x/y/releases/latest", "file:///etc/passwd",
                                 "https://api.github.com/repos/x y/releases/latest", "ftp://x"])
def test_api_url_rejected_is_warned(monkeypatch, caplog, raw):
    caplog.set_level(logging.DEBUG, logger="core.updater")
    monkeypatch.setenv(U.API_ENV, raw)
    assert U.api_url() == U.API_LATEST
    w = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(w) == 1 and U.API_ENV in w[0] and repr(raw) in w[0] and U.API_LATEST in w[0]


# ================================================================== real HTTP answers
class _H(http.server.BaseHTTPRequestHandler):
    routes = {}

    def do_GET(self):
        code, headers, body = self.routes.get(self.path, (404, {}, b'{"message":"Not Found"}'))
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def warnings_of(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_404_from_releases_latest_is_up_to_date(server, caplog):
    caplog.set_level(logging.DEBUG, logger="core.updater")
    url = server + "/repos/o/r/releases/latest"
    r = U.check_latest("1.0", url)
    assert r.status == "latest" and r.release is None
    w = warnings_of(caplog)
    assert len(w) == 1 and url in w[0] and "404" in w[0]


def test_404_elsewhere_stays_offline(server, caplog):
    caplog.set_level(logging.DEBUG, logger="core.updater")
    url = server + "/repos/o/r/releases/tags/v9.9"
    assert U.check_latest("1.0", url).status == "offline"
    w = warnings_of(caplog)
    assert len(w) == 1 and url in w[0] and "HTTPError" in w[0] and "HTTP 404" in w[0]


def test_403_rate_limit_logs_reset_time(server, caplog):
    caplog.set_level(logging.DEBUG, logger="core.updater")
    reset = int(time.time()) + 1800
    _H.routes["/rl/releases/latest"] = (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
                                        b'{"message":"API rate limit exceeded"}')
    url = server + "/rl/releases/latest"
    assert U.check_latest("1.0", url).status == "offline"
    w = warnings_of(caplog)
    when = dt.datetime.fromtimestamp(reset).astimezone().isoformat(timespec="seconds")
    assert len(w) == 1 and url in w[0] and "HTTP 403" in w[0] and "remaining 0" in w[0] and when in w[0]


def test_500_and_bad_json_and_no_server_are_offline_with_warning(server, caplog):
    caplog.set_level(logging.DEBUG, logger="core.updater")
    _H.routes["/e500/releases/latest"] = (500, {}, b"oops")
    _H.routes["/html/releases/latest"] = (200, {}, b"<html>")
    assert U.check_latest("1.0", server + "/e500/releases/latest").status == "offline"
    assert U.check_latest("1.0", server + "/html/releases/latest").status == "offline"
    assert U.check_latest("1.0", "http://127.0.0.1:1/releases/latest").status == "offline"   # refused
    w = warnings_of(caplog)
    assert len(w) == 3
    assert "HTTP 500" in w[0] and "JSONDecodeError" in w[1] and "URLError" in w[2]
    assert all("update check http://127.0.0.1" in x for x in w)


def test_normal_answer_unchanged(server):
    rel = {"tag_name": "v1.0.2", "body": "", "assets": [
        {"name": "SignatureExtractor-1.0.2-setup.exe", "browser_download_url": "https://x/a.exe"},
        {"name": "SignatureExtractor-1.0.2-setup.exe.sha256", "browser_download_url": "https://x/a.sha"}]}
    _H.routes["/ok/releases/latest"] = (200, {"Content-Type": "application/json"}, json.dumps(rel).encode())
    url = server + "/ok/releases/latest"
    r = U.check_latest("1.0.1", url)
    assert r.status == "new" and r.release.version == "1.0.2" and r.release.sha_url == "https://x/a.sha"
    assert U.check_latest("1.0.2", url).status == "latest"


# ================================================================== UI: address at start-up, 404 → «latest» note
def test_controller_logs_address_and_404_shows_latest(server, caplog, monkeypatch):
    """UpdateController without Tk (a stand-in app): address in the log, 404 → «Установлена последняя версия»."""
    from ui.updates import UpdateController

    class FakeApp:
        VERSION_STR = "1.0"

        def __init__(self):
            self.notes = []
            self.settings = type("S", (), {"data": {}, "get": lambda s, k, d=None: s.data.get(k, d),
                                           "set": lambda s, k, v: s.data.__setitem__(k, v)})()
            self.settings_page = type("P", (), {"set_update_note": lambda s, n: self.notes.append(n)})()
            self.quit = lambda: None

        def t(self, key, **kw):
            return key + ("" if not kw else ":" + ",".join(f"{k}={v}" for k, v in kw.items()))

    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv(U.API_ENV, f'"{server}/repos/o/r/releases/latest"')
    a = FakeApp()
    uc = UpdateController(a)
    assert uc.api_url == f"{server}/repos/o/r/releases/latest"
    info = [r.getMessage() for r in caplog.records if r.name == "ui.updates" and r.levelno == logging.INFO]
    assert info == [f"update check address: {uc.api_url} ({U.API_ENV})"]
    uc._checked(U.check_latest("1.0", uc.api_url), manual=True)
    assert a.notes == ["settings.update.latest:version=1.0"]           # not «settings.update.offline»
    assert a.settings.data.get("last_update_check")
