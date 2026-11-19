"""Updates through GitHub Releases (stage 5, no Tk).

* ``check_latest()`` asks ``releases/latest``, compares the tag with the running version and finds the
  installer ``SignatureExtractor-<ver>-setup.exe`` and its ``….exe.sha256`` asset.
* ``download()`` writes the installer into the temp folder (``.part`` first, then renamed), with progress
  and cancel; ``expected_sha256()`` reads the sum from the .sha256 asset, or from the release notes;
  ``verify()`` compares it with the downloaded file.  A file whose sum does not match is deleted.
* ``due()`` — the silent check on start-up runs at most once a day.

Network access goes through ``fetch`` / ``open_stream`` so tests can replace it (local http.server)."""
from __future__ import annotations

import logging
import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

log = logging.getLogger(__name__)

API_LATEST = "https://api.github.com/repos/stanislau-salavei/signature-extractor/releases/latest"
API_ENV = "SE_UPDATE_API"         # stage 6 (D7): «…/repos/<owner>/<test-repo>/releases/latest» for testing updates


def api_url() -> str:
    """``releases/latest`` of the project; the environment variable SE_UPDATE_API replaces it (update tests
    against a separate test repository, the published releases are not touched)."""
    v = (os.environ.get(API_ENV) or "").strip()
    return v if v.startswith(("https://", "http://")) else API_LATEST


USER_AGENT = "signature-extractor-updater"
TIMEOUT = 8.0
CHUNK = 64 * 1024
_HEX64 = re.compile(r"\b([0-9a-fA-F]{64})\b")


class DownloadCancelled(Exception):
    pass


class DownloadFailed(Exception):
    """Network error while downloading (shown as «Не удалось скачать обновление»)."""


def parse_version(v: str) -> Tuple[int, ...]:
    """«v1.10» → (1, 10); junk parts count as 0; an empty or wrong tag → ()."""
    v = str(v or "").strip().lstrip("vV")
    if not re.match(r"^\d", v):
        return ()
    out = []
    for p in v.split("."):
        m = re.match(r"\d+", p)
        out.append(int(m.group(0)) if m else 0)
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return tuple(out)


def is_newer(tag: str, current: str) -> bool:
    new = parse_version(tag)
    return bool(new) and new > parse_version(current)


@dataclass
class Release:
    version: str                      # «1.1» (tag without «v»)
    installer_url: Optional[str]
    installer_name: Optional[str]
    sha_url: Optional[str]
    notes: str = ""


@dataclass
class CheckResult:
    status: str                       # "new" | "latest" | "offline"
    release: Optional[Release] = None


def fetch(url: str, timeout: float = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def open_stream(url: str, timeout: float = TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def parse_release(data: dict) -> Release:
    ver = str(data.get("tag_name") or "").strip().lstrip("vV")
    want = f"SignatureExtractor-{ver}-setup.exe"
    inst = sha = None
    for a in data.get("assets") or []:
        name = str(a.get("name") or "")
        url = a.get("browser_download_url")
        if name.lower() == want.lower():
            inst = (name, url)
        elif name.lower() == (want + ".sha256").lower():
            sha = url
    return Release(ver, inst[1] if inst else None, inst[0] if inst else None, sha, str(data.get("body") or ""))


def check_latest(current: str, api_url: str = API_LATEST, fetcher: Callable[[str], bytes] = None) -> CheckResult:
    """Never raises: no network / bad answer → «offline»."""
    fetcher = fetcher or fetch
    try:
        data = json.loads(fetcher(api_url).decode("utf-8"))
        rel = parse_release(data)
    except Exception:
        log.debug("check_latest: Exception caught", exc_info=True)   # remark 81
        return CheckResult("offline")
    if is_newer(rel.version, current):
        return CheckResult("new", rel)
    return CheckResult("latest", rel)


def sha_from_text(text: str) -> Optional[str]:
    m = _HEX64.search(text or "")
    return m.group(1).lower() if m else None


def expected_sha256(rel: Release, fetcher: Callable[[str], bytes] = None) -> Optional[str]:
    """From the ``.sha256`` asset («<hash>  <file>»); if it is missing or unreadable — from the notes."""
    fetcher = fetcher or fetch
    if rel.sha_url:
        try:
            s = sha_from_text(fetcher(rel.sha_url).decode("utf-8", "replace"))
            if s:
                return s
        except Exception:
            log.warning("expected_sha256: Exception caught", exc_info=True)   # remark 81
    return sha_from_text(rel.notes)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def update_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "SignatureExtractor-update"
    d.mkdir(parents=True, exist_ok=True)
    return d


def download(rel: Release, dest_dir: Optional[Path] = None, progress: Callable[[int, int], None] = None,
             cancel: Optional[threading.Event] = None, opener=None) -> Path:
    """Download the installer.  Raises DownloadCancelled / DownloadFailed; partial files are removed."""
    if not rel.installer_url:
        raise DownloadFailed("no installer asset")
    opener = opener or open_stream
    dest_dir = Path(dest_dir) if dest_dir else update_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / (rel.installer_name or f"SignatureExtractor-{rel.version}-setup.exe")
    part = final.with_name(final.name + ".part")
    try:
        with opener(rel.installer_url) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0) if getattr(r, "headers", None) else 0
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled()
                chunk = r.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if total and done < total:
            raise DownloadFailed("connection closed early")
        if final.exists():
            final.unlink()
        os.replace(part, final)
        return final
    except DownloadCancelled:
        _rm(part)
        raise
    except DownloadFailed:
        _rm(part)
        raise
    except Exception as exc:
        _rm(part)
        raise DownloadFailed(str(exc)) from exc


def verify(path: Path, expected: Optional[str]) -> bool:
    """True when the file's SHA-256 equals ``expected``.  On a mismatch (or no sum) the file is deleted."""
    ok = bool(expected) and path.exists() and file_sha256(path) == expected.lower()
    if not ok:
        _rm(path)
    return ok


def _rm(p: Path) -> None:
    try:
        Path(p).unlink()
    except OSError:
        log.debug("_rm: OSError caught", exc_info=True)   # remark 81


# ------------------------------------------------------------------ once a day
def due(last: Optional[str], now: Optional[_dt.datetime] = None, hours: float = 24.0) -> bool:
    """``last`` = ISO time of the previous silent check (settings «last_update_check»)."""
    now = now or _dt.datetime.now()
    if not last:
        return True
    try:
        prev = _dt.datetime.fromisoformat(str(last))
    except ValueError:
        log.debug("due: ValueError caught", exc_info=True)   # remark 81
        return True
    if prev > now:               # clock moved back
        return True
    return (now - prev).total_seconds() >= hours * 3600


def now_iso(now: Optional[_dt.datetime] = None) -> str:
    return (now or _dt.datetime.now()).replace(microsecond=0).isoformat()
