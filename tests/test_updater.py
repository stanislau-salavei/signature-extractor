"""Stage 5: core/updater (no Tk, no real network)."""
import datetime as dt
import hashlib
import io
import json
import threading

import pytest

from core import updater as U


def test_versions():
    assert U.parse_version("v1.10") == (1, 10)
    assert U.parse_version("1.0.0") == (1,) == U.parse_version("1")
    assert U.parse_version("beta") == ()
    assert U.is_newer("v1.1", "1.0") and U.is_newer("1.10", "1.9")
    assert not U.is_newer("v1.0", "1.0") and not U.is_newer("0.9", "1.0") and not U.is_newer("junk", "1.0")


def _release_json(tag="v1.2", sha=True):
    assets = [{"name": f"SignatureExtractor-{tag.lstrip('v')}-setup.exe", "browser_download_url": "https://x/inst.exe"}]
    if sha:
        assets.append({"name": f"SignatureExtractor-{tag.lstrip('v')}-setup.exe.sha256",
                       "browser_download_url": "https://x/inst.sha256"})
    assets.append({"name": "Source.zip", "browser_download_url": "https://x/src.zip"})
    return {"tag_name": tag, "body": "Notes", "assets": assets}


def test_parse_release_and_check():
    rel = U.parse_release(_release_json())
    assert rel.version == "1.2" and rel.installer_url == "https://x/inst.exe" and rel.sha_url == "https://x/inst.sha256"
    new = U.check_latest("1.0", "api", lambda u: json.dumps(_release_json()).encode())
    assert new.status == "new" and new.release.version == "1.2"
    assert U.check_latest("1.2", "api", lambda u: json.dumps(_release_json()).encode()).status == "latest"

    def boom(u):
        raise OSError("no network")
    assert U.check_latest("1.0", "api", boom).status == "offline"
    assert U.check_latest("1.0", "api", lambda u: b"<html>").status == "offline"


def test_expected_sha_from_asset_or_notes():
    h = "a" * 64
    rel = U.parse_release(_release_json())
    assert U.expected_sha256(rel, lambda u: f"{h}  SignatureExtractor-1.2-setup.exe\n".encode()) == h
    rel2 = U.parse_release(dict(_release_json(sha=False), body=f"SHA-256: {h.upper()}"))
    assert U.expected_sha256(rel2, lambda u: b"") == h
    rel3 = U.parse_release(dict(_release_json(sha=False), body="nothing"))
    assert U.expected_sha256(rel3, lambda u: b"") is None


class _Resp(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(length if length is not None else len(data))}


def test_download_progress_verify_ok(tmp_path):
    data = b"MZ" + b"x" * 200_000
    rel = U.parse_release(_release_json())
    seen = []
    p = U.download(rel, tmp_path, lambda d, t: seen.append((d, t)), None, lambda u: _Resp(data))
    assert p.name == "SignatureExtractor-1.2-setup.exe" and p.read_bytes() == data
    assert seen[-1] == (len(data), len(data)) and len(seen) > 1
    assert U.verify(p, hashlib.sha256(data).hexdigest()) and p.exists()


def test_verify_mismatch_deletes(tmp_path):
    p = tmp_path / "f.exe"
    p.write_bytes(b"abc")
    assert not U.verify(p, "0" * 64) and not p.exists()
    p.write_bytes(b"abc")
    assert not U.verify(p, None) and not p.exists()


def test_download_short_read_and_cancel_remove_part(tmp_path):
    rel = U.parse_release(_release_json())
    with pytest.raises(U.DownloadFailed):
        U.download(rel, tmp_path, None, None, lambda u: _Resp(b"abc", length=1000))
    assert list(tmp_path.iterdir()) == []
    ev = threading.Event()
    ev.set()
    with pytest.raises(U.DownloadCancelled):
        U.download(rel, tmp_path, None, ev, lambda u: _Resp(b"abc"))
    assert list(tmp_path.iterdir()) == []

    def broken(u):
        raise OSError("reset")
    with pytest.raises(U.DownloadFailed):
        U.download(rel, tmp_path, None, None, broken)


def test_due_once_a_day():
    now = dt.datetime(2026, 11, 18, 12, 0)
    assert U.due(None, now) and U.due("garbage", now)
    assert not U.due("2026-11-18T01:00:00", now)
    assert U.due("2026-11-17T11:59:00", now)
