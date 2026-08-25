"""Email notification. Stdlib only (smtplib + email).

In dry-run mode (default) it writes the composed message to WORK_DIR as a .eml
file and logs a line, so the whole flow is testable with no SMTP server and no
risk of sending. A live send happens only when MAIL_DRY_RUN=false AND an SMTP
host is configured (see Config.can_send_email).
"""
import os
import smtplib
import ssl
import time
import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

log = logging.getLogger("notify")


def _guess_subtype(path: str) -> tuple:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".jpg": ("image", "jpeg"),
        ".jpeg": ("image", "jpeg"),
        ".png": ("image", "png"),
        ".mp4": ("video", "mp4"),
        ".gif": ("image", "gif"),
    }.get(ext, ("application", "octet-stream"))


def build_message(cfg, detection: dict, attachments: list) -> EmailMessage:
    """detection: dict with species, scientific, confidence, uncertain, camera,
    when (str), frigate_sublabel. attachments: list of file paths."""
    species = detection.get("species") or detection.get("frigate_label") or "an animal"
    conf = detection.get("confidence")
    uncertain = detection.get("uncertain")

    tag = f"{species}"
    if uncertain:
        tag = f"possible {species}"
    subject = f"[Field Station] {tag} at the office tree"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.mail_from
    msg["To"] = ", ".join(cfg.mail_to)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="fieldstation.local")

    conf_txt = f"{conf * 100:.0f}% confidence" if isinstance(conf, (int, float)) else "confidence n/a"
    lines = [
        f"The camera spotted {tag}.",
        "",
        f"  Species:     {species}"
        + (f" ({detection['scientific']})" if detection.get("scientific") else ""),
        f"  Confidence:  {conf_txt}" + ("  (below threshold - treat as tentative)" if uncertain else ""),
        f"  Camera:      {detection.get('camera', 'office_tree')}",
        f"  Time:        {detection.get('when', '')}",
    ]
    if detection.get("frigate_sublabel"):
        lines.append(f"  Frigate said: {detection['frigate_sublabel']}")
    lines += ["", "Clip and still attached where available."]
    if detection.get("clip_omitted"):
        where = detection.get("clip_path") or "the media folder"
        lines.append(f"(The clip was too large to attach; it's saved at {where}.)")
    lines += ["", "-- Office Tree Field Station (automated)"]
    msg.set_content("\n".join(lines))

    for path in attachments:
        if not path or not os.path.exists(path):
            continue
        maintype, subtype = _guess_subtype(path)
        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(), maintype=maintype, subtype=subtype,
                filename=os.path.basename(path),
            )
    return msg


def send(cfg, detection: dict, attachments: list) -> bool:
    """Send (or dry-run) one notification. Returns True if delivered/written."""
    msg = build_message(cfg, detection, attachments)

    if not cfg.can_send_email():
        # Dry run: persist the exact message we would have sent.
        os.makedirs(cfg.work_dir, exist_ok=True)
        stamp = int(time.time())
        out = os.path.join(cfg.work_dir, f"email_{stamp}_{detection.get('event_id','x')}.eml")
        with open(out, "wb") as f:
            f.write(bytes(msg))
        log.info("DRY RUN - email not sent. Wrote %s (to=%s subject=%r)",
                 out, cfg.mail_to, msg["Subject"])
        return True

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as s:
            s.ehlo()
            if cfg.smtp_starttls:
                s.starttls(context=ctx)
                s.ehlo()
            if cfg.smtp_user:
                s.login(cfg.smtp_user, cfg.smtp_password)
            s.send_message(msg)
        log.info("Emailed %s: %r", cfg.mail_to, msg["Subject"])
        return True
    except Exception as e:  # noqa: BLE001 - report and keep the service alive
        log.error("SMTP send failed (%s): %s", type(e).__name__, e)
        return False
