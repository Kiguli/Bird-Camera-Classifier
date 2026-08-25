"""Runtime configuration, read from environment variables (see .env.example)."""
import os


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _list(name: str, default: str) -> list:
    raw = os.environ.get(name, default) or ""
    return [x.strip() for x in raw.split(",") if x.strip()]


class Config:
    # Frigate
    frigate_url = os.environ.get("FRIGATE_URL", "http://frigate:5000").rstrip("/")

    # MQTT
    mqtt_host = os.environ.get("MQTT_HOST", "mosquitto")
    mqtt_port = _int("MQTT_PORT", 1883)
    mqtt_topic = os.environ.get("MQTT_TOPIC", "frigate/events")

    # What to act on
    target_labels = [x.lower() for x in _list("TARGET_LABELS", "bird")]
    min_event_score = _float("MIN_EVENT_SCORE", 0.60)
    min_species_confidence = _float("MIN_SPECIES_CONFIDENCE", 0.30)

    # Models
    md_version = os.environ.get("MD_VERSION", "MDV6-yolov9-c")
    md_conf_thres = _float("MD_CONF_THRES", 0.2)
    bioclip_model = os.environ.get("BIOCLIP_MODEL", "hf-hub:imageomics/bioclip-2")
    topk = _int("TOPK", 3)
    # If MegaDetector finds no animal, still classify the full frame?
    classify_full_frame_on_no_animal = _bool("CLASSIFY_FULL_FRAME_ON_NO_ANIMAL", True)
    torch_num_threads = _int("TORCH_NUM_THREADS", 0)  # 0 = leave torch default

    # Storage
    db_path = os.environ.get("DB_PATH", "/data/detections.sqlite")
    work_dir = os.environ.get("WORK_DIR", "/data/media")
    # Cap the number of per-event media sets kept on disk (oldest pruned). Stops
    # unbounded growth on a long-running deploy.
    media_keep = _int("MEDIA_KEEP", 500)

    # Queue + maintenance
    work_queue_maxsize = _int("WORK_QUEUE_MAXSIZE", 100)
    maintenance_interval = _int("MAINTENANCE_INTERVAL", 300)  # retry + cleanup sweep, seconds

    # Species candidate list (baked into the image; override to point elsewhere)
    species_file = os.environ.get(
        "SPECIES_FILE", "/app/species/davidson_county_birds.txt"
    )

    # Email. No real address is hardcoded here - real values live only in the
    # gitignored .env (kept out of the repo on purpose). An empty MAIL_TO means
    # can_send_email() stays False, so a missing .env can never email anyone.
    mail_dry_run = _bool("MAIL_DRY_RUN", True)
    mail_to = _list("MAIL_TO", "")
    mail_from = os.environ.get("MAIL_FROM", "Field Station <noreply@example.invalid>")
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = _int("SMTP_PORT", 587)
    smtp_starttls = _bool("SMTP_STARTTLS", True)
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")

    attach_clip = _bool("ATTACH_CLIP", True)
    max_attach_mb = _float("MAX_ATTACH_MB", 15.0)
    per_species_cooldown = _int("PER_SPECIES_COOLDOWN", 0)
    email_max_retries = _int("EMAIL_MAX_RETRIES", 5)

    @classmethod
    def can_send_email(cls) -> bool:
        """True only if a live send is both requested and actually configured."""
        return (
            not cls.mail_dry_run
            and bool(cls.smtp_host)
            and bool(cls.mail_to)
        )

    @classmethod
    def summary(cls) -> str:
        mode = "LIVE send" if cls.can_send_email() else "DRY RUN (no email sent)"
        return (
            f"frigate={cls.frigate_url} mqtt={cls.mqtt_host}:{cls.mqtt_port} "
            f"labels={cls.target_labels} mail={mode} to={cls.mail_to}"
        )


config = Config()
