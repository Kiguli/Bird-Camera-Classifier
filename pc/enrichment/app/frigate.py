"""Frigate 0.17 HTTP API client: fetch the snapshot, clip, and thumbnail for an
event. URLs and guards follow the grounded research spec.

Media may not be written the instant the 'end' event fires, and a 404 returns
application/json (not an image), so every fetch validates status AND content-type
and retries a few times with backoff before giving up.
"""
import logging
import os
import time

import requests

log = logging.getLogger("frigate")

_RETRY_DELAYS = (1, 2, 4)  # seconds


def _get_media(url: str, expect_prefixes: tuple, magic: bytes = b"") -> bytes:
    """GET a media URL, returning bytes only if it's really that media type."""
    last = None
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            r = requests.get(url, timeout=30)
            ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and any(ctype.startswith(p) for p in expect_prefixes):
                if magic and not r.content.startswith(magic):
                    last = f"bad magic bytes (ctype={ctype})"
                else:
                    return r.content
            else:
                last = f"status={r.status_code} ctype={ctype}"
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < len(_RETRY_DELAYS):
            time.sleep(_RETRY_DELAYS[attempt])
    log.warning("fetch failed %s (%s)", url, last)
    return b""


class FrigateClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def snapshot(self, event_id: str) -> bytes:
        # Unannotated full frame so MegaDetector sees the whole scene.
        url = f"{self.base}/api/events/{event_id}/snapshot.jpg?bbox=0&crop=0&quality=100"
        return _get_media(url, ("image/jpeg", "image/jpg"), magic=b"\xff\xd8")

    def thumbnail(self, event_id: str) -> bytes:
        url = f"{self.base}/api/events/{event_id}/thumbnail.jpg?format=ios"
        return _get_media(url, ("image/jpeg", "image/jpg"), magic=b"\xff\xd8")

    def clip(self, event_id: str) -> bytes:
        url = f"{self.base}/api/events/{event_id}/clip.mp4?padding=0"
        return _get_media(url, ("video/mp4", "application/octet-stream"))

    def save(self, data: bytes, path: str) -> str:
        if not data:
            return ""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path
