"""SQLite record of every enriched detection. Stdlib only.

Idempotency is keyed on whether the event was *emailed*, not merely seen: a prior
attempt that failed to fetch/classify/email leaves email_sent=0 and is retried,
while a successfully-emailed event is never re-sent. This is what lets the service
recover autonomously from a transient SMTP or network outage.
"""
import os
import sqlite3
import threading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    event_id           TEXT PRIMARY KEY,   -- Frigate id; idempotency key
    camera             TEXT,
    frigate_label      TEXT,
    sub_label_name     TEXT,
    sub_label_score    REAL,
    frigate_score      REAL,
    frigate_top_score  REAL,
    start_time         REAL,
    end_time           REAL,
    zones              TEXT,
    detector_conf      REAL,
    species_common     TEXT,
    species_scientific TEXT,
    species_score      REAL,
    uncertain          INTEGER DEFAULT 0,
    topk_json          TEXT,
    snapshot_path      TEXT,
    crop_path          TEXT,
    clip_path          TEXT,
    status             TEXT,
    error              TEXT,
    email_sent         INTEGER DEFAULT 0,
    email_attempts     INTEGER DEFAULT 0,
    classified_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_det_species ON detections(species_common);
CREATE INDEX IF NOT EXISTS idx_det_start ON detections(start_time);
CREATE INDEX IF NOT EXISTS idx_det_pending ON detections(email_sent, email_attempts);
"""


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(_SCHEMA)
            self._db.commit()

    def already_emailed(self, event_id: str) -> bool:
        """True only if this event was already successfully emailed."""
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM detections WHERE event_id = ? AND email_sent = 1",
                (event_id,),
            ).fetchone()
            return row is not None

    def record(self, **fields) -> None:
        """Upsert the event row (a retry overwrites an earlier incomplete row)."""
        cols = ", ".join(fields.keys())
        marks = ", ".join("?" for _ in fields)
        with self._lock:
            self._db.execute(
                f"INSERT OR REPLACE INTO detections ({cols}) VALUES ({marks})",
                tuple(fields.values()),
            )
            self._db.commit()

    def mark_emailed(self, event_id: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE detections SET email_sent = 1 WHERE event_id = ?", (event_id,)
            )
            self._db.commit()

    def bump_email_attempt(self, event_id: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE detections SET email_attempts = email_attempts + 1 WHERE event_id = ?",
                (event_id,),
            )
            self._db.commit()

    def pending_emails(self, max_attempts: int):
        """Rows the worker tried to email at least once but hasn't succeeded on,
        still under the retry cap. email_attempts >= 1 excludes brand-new rows the
        worker thread is handling right now, avoiding a double-send race."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM detections WHERE email_sent = 0 "
                "AND email_attempts >= 1 AND email_attempts < ? "
                "AND (species_common IS NOT NULL OR clip_path != '') "
                "ORDER BY start_time ASC LIMIT 50",
                (max_attempts,),
            ).fetchall()
            return [dict(r) for r in rows]

    def last_email_ts_for_species(self, species_common: str):
        with self._lock:
            row = self._db.execute(
                "SELECT start_time FROM detections WHERE species_common = ? "
                "AND email_sent = 1 ORDER BY start_time DESC LIMIT 1",
                (species_common,),
            ).fetchone()
            return row["start_time"] if row else None

    def close(self) -> None:
        with self._lock:
            self._db.close()
