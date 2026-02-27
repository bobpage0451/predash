"""One-shot IMAP ingestion into emails_raw.

Connects to an IMAP server over TLS, fetches messages newer than the
last ingested UID for a given (source, mailbox) pair, parses them with
the stdlib email library, and inserts rows into the ``emails_raw`` table.

Idempotency is guaranteed by the partial unique indexes on emails_raw:
any IntegrityError on insert is caught and the message is skipped.

Usage
-----
    cd services/worker
    python -m app.imap          # uses .env for credentials
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import imaplib
import logging
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.models import EmailRaw

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_last_uid(session, source: str, mailbox: str) -> int:
    """Return the highest imap_uid already stored for (source, mailbox)."""
    result = (
        session.query(func.max(EmailRaw.imap_uid))
        .filter(EmailRaw.source == source, EmailRaw.mailbox == mailbox)
        .scalar()
    )
    return result or 0


def _parse_internal_date(raw: bytes) -> datetime | None:
    """Parse the INTERNALDATE string returned by IMAP FETCH.

    The value comes back as something like:
        b'"18-Feb-2026 14:30:00 +0100"'
    """
    try:
        text = raw.decode("ascii", errors="replace").strip(' "')
        return imaplib.Internaldate2tuple(
            # Internaldate2tuple expects the original response token
            b'INTERNALDATE "' + text.encode() + b'"'
        )
    except Exception:
        pass

    # Fallback: try email.utils parser on the cleaned string
    try:
        text = raw.decode("ascii", errors="replace").strip(' "')
        return parsedate_to_datetime(text)
    except Exception:
        return None


def _parse_internaldate(data: dict[bytes, bytes | None]) -> datetime | None:
    """Extract INTERNALDATE from a fetch response dict."""
    raw = data.get(b"INTERNALDATE")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, bytes):
        return _parse_internal_date(raw)
    return None


def _extract_body(msg: email.message.Message) -> tuple[str | None, str | None]:
    """Return (text_plain, text_html) from an email message."""
    text_plain: str | None = None
    text_html: str | None = None

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and text_plain is None:
                text_plain = _decode_payload(part)
            elif ct == "text/html" and text_html is None:
                text_html = _decode_payload(part)
    else:
        ct = msg.get_content_type()
        if ct == "text/plain":
            text_plain = _decode_payload(msg)
        elif ct == "text/html":
            text_html = _decode_payload(msg)

    return text_plain, text_html


def _decode_payload(part: email.message.Message) -> str | None:
    """Best-effort decode of a MIME part payload."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return None
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def _build_headers_dict(msg: email.message.Message) -> dict[str, list[str]]:
    """Build a JSON-serialisable dict of headers."""
    headers: dict[str, list[str]] = {}
    for key in msg.keys():
        headers.setdefault(key, []).append(str(msg[key]))
    return headers


def _parse_date_header(msg: email.message.Message) -> datetime | None:
    """Parse the Date header into a timezone-aware datetime."""
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ---------------------------------------------------------------------------
# IMAP helpers
# ---------------------------------------------------------------------------

_UID_RE = re.compile(rb"UID\s+(\d+)", re.IGNORECASE)


def _extract_uid(fetch_response: bytes) -> int | None:
    """Pull the UID integer out of a FETCH response line."""
    m = _UID_RE.search(fetch_response)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the one-shot IMAP ingestion."""
    load_dotenv()

    # ── Config ──────────────────────────────────────────────────────────
    imap_host = os.environ.get("IMAP_HOST", "mail.eclipso.de")
    imap_port = int(os.environ.get("IMAP_PORT", "993"))
    imap_user = os.environ.get("IMAP_USER")
    imap_pass = os.environ.get("IMAP_PASS")
    mailbox = os.environ.get("IMAP_MAILBOX", "INBOX")
    source = os.environ.get("EMAIL_SOURCE", f"eclipso:{imap_user}")
    limit_str = os.environ.get("IMAP_LIMIT")
    limit = int(limit_str) if limit_str else None

    if not imap_user or not imap_pass:
        log.error("IMAP_USER and IMAP_PASS must be set.")
        sys.exit(1)

    log.info("source=%s  mailbox=%s  host=%s:%d", source, mailbox, imap_host, imap_port)

    # ── DB: derive last UID ─────────────────────────────────────────────
    Session = get_session()
    with Session() as session:
        last_uid = _get_last_uid(session, source, mailbox)

    log.info("last_uid=%d", last_uid)

    # ── IMAP connect ────────────────────────────────────────────────────
    log.info("Connecting to %s:%d …", imap_host, imap_port)
    imap = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        imap.login(imap_user, imap_pass)
        log.info("Logged in as %s", imap_user)

        status, _ = imap.select(mailbox, readonly=True)
        if status != "OK":
            log.error("Could not select mailbox %s", mailbox)
            sys.exit(1)

        # ── Search for UIDs > last_uid ──────────────────────────────────
        search_criterion = f"UID {last_uid + 1}:*"
        status, data = imap.uid("SEARCH", None, search_criterion)
        if status != "OK" or not data or not data[0]:
            log.info("No new messages found.")
            return

        uid_list = [int(u) for u in data[0].split()]
        # IMAP UID SEARCH is inclusive and may return last_uid itself
        uid_list = [u for u in uid_list if u > last_uid]

        if not uid_list:
            log.info("No new messages (after filtering).")
            return

        uid_list.sort()

        if limit:
            # Keep the newest N UIDs
            uid_list = uid_list[-limit:]
            log.info("IMAP_LIMIT=%d, trimmed to %d UIDs", limit, len(uid_list))

        log.info("Found %d new UID(s): %d … %d", len(uid_list), uid_list[0], uid_list[-1])

        # ── Fetch & insert ──────────────────────────────────────────────
        inserted = 0
        skipped = 0

        for uid in uid_list:
            uid_str = str(uid)
            status, fetch_data = imap.uid("FETCH", uid_str, "(RFC822 INTERNALDATE)")
            if status != "OK" or not fetch_data:
                log.warning("UID %s: FETCH failed, skipping", uid_str)
                skipped += 1
                continue

            # fetch_data is a list; the message is in the first tuple element
            raw_email: bytes | None = None
            internal_date: datetime | None = None

            for item in fetch_data:
                if isinstance(item, tuple) and len(item) == 2:
                    raw_email = item[1]
                    # Parse INTERNALDATE from the response line
                    resp_line = item[0]
                    idate_match = re.search(
                        rb'INTERNALDATE "([^"]+)"', resp_line
                    )
                    if idate_match:
                        try:
                            internal_date = imaplib.Internaldate2tuple(resp_line)
                            if internal_date is not None:
                                # imaplib returns a time.struct_time; convert
                                import time as _time
                                internal_date = datetime(
                                    *internal_date[:6], tzinfo=timezone.utc
                                )
                        except Exception:
                            pass
                    break

            if raw_email is None:
                log.warning("UID %s: no RFC822 data, skipping", uid_str)
                skipped += 1
                continue

            # Parse
            msg = email.message_from_bytes(raw_email, policy=email.policy.default)
            message_id = msg.get("Message-ID")
            if message_id:
                message_id = str(message_id).strip()
            from_addr = str(msg.get("From", "")).strip() or None
            subject = str(msg.get("Subject", "")).strip() or None
            date_sent = _parse_date_header(msg)
            body_text, body_html = _extract_body(msg)
            raw_headers = _build_headers_dict(msg)
            sha = hashlib.sha256(raw_email).hexdigest()

            row = EmailRaw(
                source=source,
                mailbox=mailbox,
                message_id=message_id,
                imap_uid=uid,
                from_addr=from_addr,
                subject=subject,
                date_sent=date_sent,
                date_received=internal_date,
                body_text=body_text,
                body_html=body_html,
                raw_headers=raw_headers,
                sha256=sha,
            )

            with Session() as session:
                try:
                    session.add(row)
                    session.commit()
                    inserted += 1
                except IntegrityError:
                    session.rollback()
                    log.debug("UID %s: duplicate, skipped (IntegrityError)", uid_str)
                    skipped += 1

        # ── Summary ─────────────────────────────────────────────────────
        with Session() as session:
            final_uid = _get_last_uid(session, source, mailbox)

        log.info(
            "Done. fetched=%d  inserted=%d  skipped=%d  final_max_uid=%d",
            len(uid_list),
            inserted,
            skipped,
            final_uid,
        )

    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
