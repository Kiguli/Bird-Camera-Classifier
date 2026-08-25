"""Office Tree Field Station - enrichment + notification service.

Subscribes to Frigate's MQTT events; on each finished (type=="end") event whose
label we care about and whose score clears the threshold, fetches the snapshot and
clip, crops with MegaDetector v6, classifies the species with BioCLIP 2 against the
Davidson County list, records the result to SQLite, and emails interested parties
the clip + classification.

Runs unattended: it keeps going through partial failures (a model, a fetch, or an
SMTP send can fail and the event is still logged), uses a persistent MQTT session
so events aren't lost across brief restarts, retries failed emails on a timer, and
prunes saved media so disk use stays bounded.
"""
import io
import json
import logging
import os
import queue
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from PIL import Image

from app.config import config
from app.store import Store
from app.frigate import FrigateClient
from app.detector import Detector
from app.classifier import Classifier, load_species
from app import notify

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")

work_q: "queue.Queue" = queue.Queue(maxsize=config.work_queue_maxsize)
_dropped = 0
_last_drop_log = 0.0


# ---- MQTT callbacks (network thread: parse + filter + enqueue only) ----------
def on_connect(client, userdata, flags, reason_code, properties):
    # qos=1 + a persistent session (clean_session=False) means the broker queues
    # events for us across a brief outage instead of dropping them.
    log.info("MQTT connected (%s); subscribing to %s", reason_code, config.mqtt_topic)
    client.subscribe(config.mqtt_topic, qos=1)


def _event_score(after: dict) -> float:
    # top_score is the peak score over the track; more meaningful at 'end' than the
    # instantaneous last-frame score.
    for key in ("top_score", "score"):
        v = after.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def on_message(client, userdata, msg):
    global _dropped, _last_drop_log
    try:
        payload = json.loads(msg.payload)
    except Exception:
        return
    if payload.get("type") != "end":
        return
    after = payload.get("after") or {}
    if (after.get("label") or "").lower() not in config.target_labels:
        return
    if after.get("end_time") is None:  # finalized check
        return
    if _event_score(after) < config.min_event_score:
        return
    try:
        work_q.put_nowait(after)
    except queue.Full:
        try:
            work_q.get_nowait()  # drop oldest to bound memory
        except queue.Empty:
            pass
        try:
            work_q.put_nowait(after)
        except queue.Full:
            pass
        _dropped += 1
        now = time.time()
        if now - _last_drop_log > 30:  # rate-limit the warning
            log.warning("work queue full - dropped %d event(s) so far (qsize=%d). "
                        "Consumer can't keep up; consider raising WORK_QUEUE_MAXSIZE "
                        "or reducing load.", _dropped, work_q.qsize())
            _last_drop_log = now


# ---- helpers -----------------------------------------------------------------
def _sub_label(after: dict):
    sl = after.get("sub_label")
    if isinstance(sl, (list, tuple)) and sl:
        name = sl[0]
        score = sl[1] if len(sl) > 1 and isinstance(sl[1], (int, float)) else None
        return name, score
    if isinstance(sl, str):
        return sl, None
    return None, None


def _fmt_time(epoch):
    try:
        return datetime.fromtimestamp(float(epoch)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _attachments_for(clip_path, crop_path, snapshot_path):
    """Pick attachments under the size cap; report whether the clip was omitted."""
    attachments, clip_omitted = [], False
    if clip_path and os.path.exists(clip_path):
        if config.attach_clip and (os.path.getsize(clip_path) / 1e6) <= config.max_attach_mb:
            attachments.append(clip_path)
        else:
            clip_omitted = True
    image = crop_path or snapshot_path
    if image and os.path.exists(image) and (os.path.getsize(image) / 1e6) <= config.max_attach_mb:
        attachments.append(image)
    return attachments, clip_omitted


# ---- worker thread -----------------------------------------------------------
def worker(frigate, detector, clf, store):
    while True:
        after = work_q.get()
        if after is None:
            return
        event_id = after.get("id", "unknown")
        try:
            _process(after, event_id, frigate, detector, clf, store)
        except Exception as e:  # noqa: BLE001 - never let one event kill the worker
            log.exception("event %s failed", event_id)
            try:
                store.record(event_id=event_id, camera=after.get("camera"),
                             status="error", error=f"{type(e).__name__}: {e}",
                             classified_at=datetime.now().isoformat())
            except Exception:
                pass
        finally:
            work_q.task_done()


def _process(after, event_id, frigate, detector, clf, store):
    if store.already_emailed(event_id):
        log.info("event %s already emailed - skipping", event_id)
        return

    camera = after.get("camera")
    label = after.get("label")
    sub_name, sub_score = _sub_label(after)
    os.makedirs(config.work_dir, exist_ok=True)

    snap_bytes = frigate.snapshot(event_id) if after.get("has_snapshot") else b""
    used_fallback = False
    if not snap_bytes:
        snap_bytes = frigate.thumbnail(event_id)
        used_fallback = bool(snap_bytes)

    snapshot_path = crop_path = clip_path = ""
    detector_conf = species_common = species_sci = species_score = None
    topk = []
    status = "ok"

    if not snap_bytes:
        status = "no_snapshot"
        log.warning("event %s: no snapshot or thumbnail", event_id)
    else:
        snapshot_path = frigate.save(snap_bytes, os.path.join(config.work_dir, f"{event_id}_snap.jpg"))
        try:
            img = Image.open(io.BytesIO(snap_bytes)).convert("RGB")
        except Exception as e:  # noqa: BLE001
            img = None
            status = "fetch_failed"
            log.warning("event %s: snapshot not decodable (%s)", event_id, e)

        if img is not None:
            crop, detector_conf = detector.crop_best_animal(img)
            target = crop
            if crop is not None:
                crop_path = frigate.save(_to_jpeg(crop), os.path.join(config.work_dir, f"{event_id}_crop.jpg"))
            elif detector.available:
                status = "no_animal"
                target = img if config.classify_full_frame_on_no_animal else None
            else:
                target = img  # detector unavailable -> classify full frame

            if target is not None and clf.available:
                topk = clf.classify(target, k=config.topk)
                if topk:
                    species_common, species_sci, species_score = topk[0]
                    if status == "no_animal":
                        status = "ok_full_frame"  # classified the full frame despite no crop
            elif not clf.available:
                status = "model_unavailable"

    uncertain = 1 if (species_score is not None and species_score < config.min_species_confidence) else 0

    clip_bytes = frigate.clip(event_id) if after.get("has_clip") else b""
    if clip_bytes:
        clip_path = frigate.save(clip_bytes, os.path.join(config.work_dir, f"{event_id}.mp4"))

    store.record(
        event_id=event_id, camera=camera, frigate_label=label,
        sub_label_name=sub_name, sub_label_score=sub_score,
        frigate_score=after.get("score"), frigate_top_score=after.get("top_score"),
        start_time=after.get("start_time"), end_time=after.get("end_time"),
        zones=json.dumps(after.get("current_zones") or []),
        detector_conf=detector_conf,
        species_common=species_common, species_scientific=species_sci,
        species_score=species_score, uncertain=uncertain,
        topk_json=json.dumps(topk),
        snapshot_path=snapshot_path, crop_path=crop_path, clip_path=clip_path,
        status=status, classified_at=datetime.now().isoformat(),
    )
    log.info("event %s: label=%s species=%s score=%s status=%s%s",
             event_id, label, species_common, species_score, status,
             " (thumbnail fallback)" if used_fallback else "")

    # per-species cooldown
    if species_common and config.per_species_cooldown > 0:
        last = store.last_email_ts_for_species(species_common)
        if last and (time.time() - last) < config.per_species_cooldown:
            log.info("event %s: within cooldown for %s - not emailing", event_id, species_common)
            return

    attachments, clip_omitted = _attachments_for(clip_path, crop_path, snapshot_path)
    detection = dict(
        event_id=event_id, species=species_common, scientific=species_sci,
        confidence=species_score, uncertain=uncertain, camera=camera,
        when=_fmt_time(after.get("start_time")),
        frigate_sublabel=sub_name, frigate_label=label,
        clip_omitted=clip_omitted, clip_path=clip_path,
    )
    # First attempt is the worker's; the maintenance thread retries from attempt 2.
    store.bump_email_attempt(event_id)
    if notify.send(config, detection, attachments):
        store.mark_emailed(event_id)


def _to_jpeg(pil_img) -> bytes:
    buf = io.BytesIO()
    pil_img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ---- maintenance thread: retry failed emails + prune media -------------------
def maintenance(store):
    while True:
        time.sleep(config.maintenance_interval)
        try:
            _retry_pending(store)
        except Exception:
            log.exception("email retry sweep failed")
        try:
            _prune_media()
        except Exception:
            log.exception("media prune failed")


def _retry_pending(store):
    rows = store.pending_emails(config.email_max_retries)
    for row in rows:
        eid = row["event_id"]
        attachments, clip_omitted = _attachments_for(
            row.get("clip_path"), row.get("crop_path"), row.get("snapshot_path"))
        detection = dict(
            event_id=eid, species=row.get("species_common"),
            scientific=row.get("species_scientific"), confidence=row.get("species_score"),
            uncertain=row.get("uncertain"), camera=row.get("camera"),
            when=_fmt_time(row.get("start_time")),
            frigate_sublabel=row.get("sub_label_name"), frigate_label=row.get("frigate_label"),
            clip_omitted=clip_omitted, clip_path=row.get("clip_path"),
        )
        store.bump_email_attempt(eid)
        if notify.send(config, detection, attachments):
            store.mark_emailed(eid)
            log.info("event %s: email retry succeeded", eid)
        else:
            log.warning("event %s: email retry failed (attempt %d)", eid, (row.get("email_attempts") or 0) + 1)


def _prune_media():
    """Keep disk bounded: retain the newest media_keep*4 files, delete older."""
    d = config.work_dir
    if not os.path.isdir(d):
        return
    files = [os.path.join(d, f) for f in os.listdir(d)]
    files = [f for f in files if os.path.isfile(f)]
    limit = max(config.media_keep * 4, 40)
    if len(files) <= limit:
        return
    files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    for f in files[limit:]:
        try:
            os.remove(f)
        except OSError:
            pass
    log.info("pruned %d old media files (kept %d)", len(files) - limit, limit)


def main():
    log.info("Starting enrichment service. %s", config.summary())
    species = load_species(config.species_file)
    log.info("Loaded %d candidate species from %s", len(species), config.species_file)

    store = Store(config.db_path)
    frigate = FrigateClient(config.frigate_url)
    detector = Detector(config.md_version, config.md_conf_thres)
    clf = Classifier(config.bioclip_model, species, config.torch_num_threads)

    if not clf.available:
        log.warning("Species classification is OFF (model unavailable) - events "
                    "will still be logged and emailed with Frigate's own label.")

    threading.Thread(target=worker, args=(frigate, detector, clf, store), daemon=True).start()
    threading.Thread(target=maintenance, args=(store,), daemon=True).start()

    # Persistent session so QoS-1 events queue at the broker across brief restarts.
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bird-classifier",
                         clean_session=False)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    while True:
        try:
            client.connect(config.mqtt_host, config.mqtt_port, keepalive=60)
            break
        except Exception as e:  # noqa: BLE001 - broker may still be starting
            log.warning("MQTT connect failed (%s) - retrying in 5s", e)
            time.sleep(5)
    client.loop_forever()


if __name__ == "__main__":
    main()
