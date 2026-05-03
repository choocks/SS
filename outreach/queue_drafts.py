"""Cold-email draft queueing — Gmail API.

Reads prospects.csv, personalizes one of three sequence emails, and creates
Gmail DRAFTS (never sends). Operator reviews each draft and sends manually.

Hard rules enforced:
- Drafts only. The script has no "send" code path.
- Per-inbox daily cap of 20. Refuses to exceed it for a given inbox/day.
- Plain text only. No HTML, no tracking pixels, no link shorteners.
- Sequences 2 and 3 thread as replies inside the original (sequence 1) thread.
- sent_log.csv dedupes (prospect_email, sequence): re-running the same args
  on the same prospects creates zero new drafts.

Usage:
    python outreach/queue_drafts.py --csv prospects.csv \\
        --inbox anthony@domain.co --sequence 1 --limit 20

    # Validate templates / preview what would happen, no API calls:
    python outreach/queue_drafts.py --csv prospects.csv \\
        --inbox anthony@domain.co --sequence 1 --dry-run
"""

from __future__ import annotations

import argparse
import base64
import csv
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, date, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

DAILY_CAP_DEFAULT = 20

OUTREACH_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = OUTREACH_DIR / "templates"
SENT_LOG_PATH = OUTREACH_DIR / "sent_log.csv"

SENT_LOG_COLUMNS = [
    "prospect_email",
    "sequence",
    "draft_id",
    "queued_at",
    "inbox",
    "thread_id",
]

WORD_LIMITS = {1: 75, 2: 100, 3: 50}

VERTICAL_HUMANIZE = {
    "med_spa": "med spa",
    "dental": "dental",
    "personal_injury_law": "personal injury law",
    "family_law": "family law",
    "hvac": "HVAC",
    "roofing": "roofing",
    "solar": "solar",
    "chiropractor": "chiropractor",
}


# --- Email template loading + personalization --------------------------------


@dataclass
class Email:
    subject: str
    body: str

    def word_count(self) -> int:
        return len(re.findall(r"[\w'\-]+", self.body))


def humanize_vertical(v: str) -> str:
    if not v:
        return ""
    return VERTICAL_HUMANIZE.get(v, v.replace("_", " "))


def load_template(sequence: int, templates_dir: Path = TEMPLATES_DIR) -> Email:
    path = templates_dir / f"email_{sequence}.txt"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].lower().startswith("subject:"):
        raise ValueError(f"{path}: first line must be 'Subject: ...'")
    subject = lines[0][len("Subject:"):].strip()
    i = 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    body = "\n".join(lines[i:]).rstrip() + "\n"
    return Email(subject=subject, body=body)


_TOKEN_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def render(email: Email, prospect: dict) -> Email:
    """Replace personalization tokens. Falls back owner_first_name to 'there'."""
    tokens: dict[str, str] = {
        "owner_first_name": (prospect.get("owner_first_name") or "").strip() or "there",
        "business_name": (prospect.get("business_name") or "").strip() or "your team",
        "vertical": humanize_vertical((prospect.get("vertical") or "").strip()),
        "city": (prospect.get("city") or "").strip(),
        "ad_platform": (prospect.get("ad_platform") or "").strip() or "paid",
        "ad_evidence_url": (prospect.get("ad_evidence_url") or "").strip(),
    }

    def sub(text: str) -> str:
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in tokens:
                raise ValueError(f"unknown token {{{{{key}}}}} in template")
            return tokens[key]
        return _TOKEN_RE.sub(repl, text)

    return Email(subject=sub(email.subject), body=sub(email.body))


# --- Sent log ----------------------------------------------------------------


def load_sent_log(path: Path = SENT_LOG_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=SENT_LOG_COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in SENT_LOG_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[SENT_LOG_COLUMNS]


def append_sent_log(rows: list[dict[str, str]], path: Path = SENT_LOG_PATH) -> None:
    if not rows:
        return
    new_df = pd.DataFrame(rows, columns=SENT_LOG_COLUMNS)
    if path.exists():
        existing = pd.read_csv(path, dtype=str).fillna("")
        merged = pd.concat([existing, new_df], ignore_index=True)
    else:
        merged = new_df
    merged.to_csv(path, index=False)


def already_drafted(log: pd.DataFrame, email_addr: str, sequence: int) -> bool:
    if log.empty:
        return False
    matches = log[
        (log["prospect_email"].str.lower() == email_addr.lower())
        & (log["sequence"].astype(str) == str(sequence))
    ]
    return not matches.empty


def drafts_today(log: pd.DataFrame, inbox: str) -> int:
    if log.empty:
        return 0
    today_iso = date.today().isoformat()
    matches = log[
        (log["inbox"].str.lower() == inbox.lower())
        & (log["queued_at"].str.startswith(today_iso))
    ]
    return len(matches)


# --- Gmail client ------------------------------------------------------------


class GmailClient:
    """Thin wrapper over the Gmail API for creating draft emails.

    Authenticates per-inbox and caches OAuth tokens under GMAIL_TOKEN_DIR.
    """

    def __init__(self, inbox: str, *, credentials_path: str, token_dir: str):
        self.inbox = inbox
        self.credentials_path = credentials_path
        self.token_dir = Path(token_dir)
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self._service = None

    def _build_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_path = self.token_dir / f"{self.inbox.replace('@', '_at_')}.json"
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(self.credentials_path).exists():
                    raise FileNotFoundError(
                        f"Gmail OAuth client secrets not found at {self.credentials_path}. "
                        "Set GMAIL_CREDENTIALS_PATH in .env or pass --credentials."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def find_thread_id(self, prospect_email: str, original_subject: str) -> str | None:
        """Find the most recent thread sent TO prospect with the given subject.

        Used by sequences 2 and 3 to thread replies into the original outreach.
        """
        q = f'to:{prospect_email} subject:"{original_subject}"'
        resp = (
            self.service.users()
            .threads()
            .list(userId="me", q=q, maxResults=5)
            .execute()
        )
        threads = resp.get("threads") or []
        if not threads:
            return None
        return threads[0].get("id")

    def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        in_reply_to_message_id: str | None = None,
    ) -> dict[str, str]:
        msg = MIMEText(body, _charset="utf-8")
        msg["to"] = to
        msg["from"] = self.inbox
        msg["subject"] = subject
        if in_reply_to_message_id:
            msg["In-Reply-To"] = in_reply_to_message_id
            msg["References"] = in_reply_to_message_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        body_dict: dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            body_dict["message"]["threadId"] = thread_id

        draft = (
            self.service.users()
            .drafts()
            .create(userId="me", body=body_dict)
            .execute()
        )
        return {
            "draft_id": draft.get("id", ""),
            "thread_id": draft.get("message", {}).get("threadId", ""),
        }

    def latest_message_id_in_thread(self, thread_id: str) -> str | None:
        resp = (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=["Message-ID"])
            .execute()
        )
        messages = resp.get("messages") or []
        if not messages:
            return None
        for header in messages[-1].get("payload", {}).get("headers", []):
            if header.get("name", "").lower() == "message-id":
                return header.get("value")
        return None


# --- Dry-run client (for testing without API access) -------------------------


class DryRunGmailClient:
    """Stand-in that prints what would happen, without touching Gmail."""

    def __init__(self, inbox: str):
        self.inbox = inbox
        self._counter = 0

    def find_thread_id(self, prospect_email: str, original_subject: str) -> str | None:
        # In dry-run we pretend a thread exists, so threading logic exercises.
        # This means the operator's real sequence-2 run is the first time
        # threading actually happens.
        return f"DRY_THREAD_{abs(hash(prospect_email))}"

    def latest_message_id_in_thread(self, thread_id: str) -> str | None:
        return f"<DRY_MSGID_{thread_id}@dry-run>"

    def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
        in_reply_to_message_id: str | None = None,
    ) -> dict[str, str]:
        self._counter += 1
        draft_id = f"DRY_DRAFT_{self._counter:04d}"
        print(f"\n--- DRY-RUN DRAFT {self._counter} ({draft_id}) ---")
        print(f"From:    {self.inbox}")
        print(f"To:      {to}")
        print(f"Subject: {subject}")
        if thread_id:
            print(f"Thread:  {thread_id}")
        if in_reply_to_message_id:
            print(f"In-Reply-To: {in_reply_to_message_id}")
        print()
        print(body.rstrip())
        print("--- end draft ---")
        return {"draft_id": draft_id, "thread_id": thread_id or ""}


# --- Orchestration -----------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--csv", required=True, help="Path to prospects.csv")
    p.add_argument(
        "--inbox",
        required=True,
        help="Sending Gmail/Workspace address (must be authenticated for OAuth).",
    )
    p.add_argument(
        "--sequence",
        type=int,
        required=True,
        choices=[1, 2, 3],
        help="Which email in the sequence (1=hook, 2=offer, 3=breakup).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=DAILY_CAP_DEFAULT,
        help=f"Max drafts to create this run (default {DAILY_CAP_DEFAULT}).",
    )
    p.add_argument(
        "--daily-cap",
        type=int,
        default=DAILY_CAP_DEFAULT,
        help=f"Hard ceiling on drafts per inbox per day (default {DAILY_CAP_DEFAULT}).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Gmail API; print drafts to stdout. Still writes to sent_log.csv "
             "so dedupe behavior is testable.",
    )
    p.add_argument(
        "--log-path",
        default=None,
        help="Override path to sent_log.csv (defaults to outreach/sent_log.csv).",
    )
    p.add_argument(
        "--credentials",
        default=None,
        help="Path to Gmail OAuth client_secret JSON. Defaults to GMAIL_CREDENTIALS_PATH env.",
    )
    p.add_argument(
        "--token-dir",
        default=None,
        help="Directory for cached OAuth tokens. Defaults to GMAIL_TOKEN_DIR env.",
    )
    return p.parse_args(argv)


def load_prospects(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise SystemExit(f"prospects CSV not found: {csv_path}")
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    return df.to_dict("records")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    csv_path = Path(args.csv)
    prospects = load_prospects(csv_path)
    template = load_template(args.sequence)

    log_path = Path(args.log_path) if args.log_path else SENT_LOG_PATH

    body_words = template.word_count()
    if body_words >= WORD_LIMITS[args.sequence]:
        raise SystemExit(
            f"template email_{args.sequence}.txt is {body_words} words "
            f"(limit < {WORD_LIMITS[args.sequence]}). Trim before queueing."
        )

    log = load_sent_log(log_path)
    queued_today = drafts_today(log, args.inbox)
    daily_remaining = max(0, args.daily_cap - queued_today)
    if daily_remaining == 0:
        print(
            f"Daily cap reached: {queued_today}/{args.daily_cap} for {args.inbox} "
            f"on {date.today().isoformat()}. Aborting."
        )
        return 0
    effective_limit = min(args.limit, daily_remaining)
    if effective_limit < args.limit:
        print(
            f"Capping at {effective_limit} (daily room remaining: {daily_remaining}, "
            f"already queued today: {queued_today})."
        )

    if args.dry_run:
        client: Any = DryRunGmailClient(args.inbox)
    else:
        creds_path = args.credentials or os.getenv(
            "GMAIL_CREDENTIALS_PATH", "./gmail_credentials.json"
        )
        token_dir = args.token_dir or os.getenv("GMAIL_TOKEN_DIR", "./.gmail_tokens")
        client = GmailClient(args.inbox, credentials_path=creds_path, token_dir=token_dir)

    seq1_template = load_template(1) if args.sequence > 1 else None

    new_log_rows: list[dict[str, str]] = []
    skipped_no_email = 0
    skipped_already = 0
    skipped_no_thread = 0
    created = 0

    for prospect in prospects:
        if created >= effective_limit:
            break
        email_addr = (prospect.get("email") or "").strip()
        if not email_addr:
            skipped_no_email += 1
            continue
        if already_drafted(log, email_addr, args.sequence):
            skipped_already += 1
            continue

        try:
            rendered = render(template, prospect)
        except ValueError as e:
            print(f"  skip {email_addr}: render failed — {e}")
            continue

        if rendered.word_count() >= WORD_LIMITS[args.sequence]:
            print(
                f"  skip {email_addr}: rendered body has {rendered.word_count()} "
                f"words, limit {WORD_LIMITS[args.sequence]}"
            )
            continue

        thread_id: str | None = None
        in_reply_to: str | None = None
        if args.sequence > 1 and seq1_template is not None:
            seq1_rendered = render(seq1_template, prospect)
            thread_id = client.find_thread_id(email_addr, seq1_rendered.subject)
            if not thread_id:
                skipped_no_thread += 1
                print(
                    f"  skip {email_addr}: no sequence-1 thread found "
                    f"(have you sent sequence 1 to this prospect?)"
                )
                continue
            in_reply_to = client.latest_message_id_in_thread(thread_id)

        result = client.create_draft(
            to=email_addr,
            subject=rendered.subject,
            body=rendered.body,
            thread_id=thread_id,
            in_reply_to_message_id=in_reply_to,
        )
        created += 1
        new_log_rows.append(
            {
                "prospect_email": email_addr,
                "sequence": str(args.sequence),
                "draft_id": result.get("draft_id", ""),
                "queued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "inbox": args.inbox,
                "thread_id": result.get("thread_id", "") or (thread_id or ""),
            }
        )

    append_sent_log(new_log_rows, log_path)

    print()
    print(
        f"Sequence {args.sequence}: created {created} draft(s) "
        f"(inbox: {args.inbox}, dry-run: {args.dry_run})"
    )
    print(
        f"  skipped — no email: {skipped_no_email}, "
        f"already drafted: {skipped_already}, "
        f"no thread: {skipped_no_thread}"
    )
    print(f"  log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
