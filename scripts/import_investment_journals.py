#!/usr/bin/env python3
"""Import investment journal markdown files into the crypto-diary Google Sheet.

The Streamlit app is intentionally read-only. This script is a local/operator tool
for writing historical daily investment plans into the canonical Google Sheet.
It never contains credentials; it reads the same local service-account file used
by the investment bot, or paths/IDs provided through environment variables.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("CRYPTO_BOT_SHEET_ID", "15etJTSEw2BmN1zI2mSHdshT8U7MCujRRAO2l86ZgARQ")
CRED_PATH = Path(
    os.environ.get(
        "CRYPTO_BOT_GCP_CRED",
        "/Users/mike-hermes-ai/.hermes/crypto_bot/gcp_service_account.json",
    )
)
WORKSHEET = os.environ.get("CRYPTO_BOT_JOURNAL_WORKSHEET", "journal_entries")
AI_JOURNAL_REPO = Path(os.environ.get("AI_INVESTMENT_JOURNAL_DIR", "/Users/mike-hermes-ai/ai-investment-journal")).expanduser()
CRON_OUTPUT_DIR = Path(os.environ.get("HERMES_INVESTMENT_CRON_OUTPUT", "/Users/mike-hermes-ai/.hermes/cron/output/751ec9850858")).expanduser()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
HEADER = [
    "date",
    "run_time",
    "category",
    "source",
    "title",
    "summary",
    "content_markdown",
    "github_path",
    "cron_output_path",
    "tags",
]


@dataclass(frozen=True)
class JournalRow:
    date: str
    run_time: str
    category: str
    source: str
    title: str
    summary: str
    content_markdown: str
    github_path: str
    cron_output_path: str
    tags: str

    def as_sheet_row(self) -> list[str]:
        return [getattr(self, field) for field in HEADER]


def get_worksheet():
    if not CRED_PATH.exists():
        raise FileNotFoundError(f"Service-account credential not found: {CRED_PATH}")
    creds = Credentials.from_service_account_file(CRED_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=WORKSHEET, rows=1000, cols=len(HEADER))
        worksheet.append_row(HEADER)
    values = worksheet.get_all_values()
    if not values:
        worksheet.append_row(HEADER)
    elif values[0] != HEADER:
        raise ValueError(f"Unexpected header in worksheet {WORKSHEET}: {values[0]}")
    return worksheet


def extract_date_from_name(path: Path) -> str:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"Cannot infer date from {path}")
    return match.group(1)


def first_heading(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def summarize(markdown: str, max_chars: int = 220) -> str:
    lines = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        if line.startswith("|") and "---" in line:
            continue
        lines.append(line)
        if len(" ".join(lines)) >= max_chars:
            break
    text = " ".join(lines)
    return text[: max_chars - 1] + "…" if len(text) > max_chars else text


def parse_cron_run_time(markdown: str) -> str:
    match = re.search(r"\*\*Run Time:\*\*\s*(.+)", markdown)
    return match.group(1).strip() if match else ""


def response_section(markdown: str) -> str:
    marker = "## Response"
    if marker in markdown:
        return markdown.split(marker, 1)[1].strip()
    return markdown.strip()


def collect_rows() -> list[JournalRow]:
    rows: list[JournalRow] = []

    for path in sorted((AI_JOURNAL_REPO / "daily").glob("20*.md")):
        content = path.read_text(encoding="utf-8")
        date = extract_date_from_name(path)
        rows.append(
            JournalRow(
                date=date,
                run_time="09:00 Asia/Taipei",
                category="Crypto, ETF",
                source="ai-investment-journal/daily",
                title=first_heading(content, f"每日投資決策 — {date}"),
                summary=summarize(content),
                content_markdown=content,
                github_path=f"daily/{path.name}",
                cron_output_path="",
                tags="daily-schedule,investment-plan,crypto,etf",
            )
        )

    for path in sorted((AI_JOURNAL_REPO / "shadow").glob("20*.md")):
        content = path.read_text(encoding="utf-8")
        date = extract_date_from_name(path)
        rows.append(
            JournalRow(
                date=date,
                run_time="09:00 Asia/Taipei",
                category="Crypto",
                source="ai-invest-robot/shadow",
                title=first_heading(content, f"Shadow 投資日誌 — {date}"),
                summary=summarize(content),
                content_markdown=content,
                github_path=f"shadow/{path.name}",
                cron_output_path="",
                tags="shadow-mode,crypto,investment-plan",
            )
        )

    for path in sorted(CRON_OUTPUT_DIR.glob("20*.md")):
        raw = path.read_text(encoding="utf-8")
        content = response_section(raw)
        date = extract_date_from_name(path)
        rows.append(
            JournalRow(
                date=date,
                run_time=parse_cron_run_time(raw),
                category="Crypto, ETF",
                source="Hermes cron daily-investment-journal",
                title=first_heading(content, f"每日投資排程紀錄 — {date}"),
                summary=summarize(content),
                content_markdown=content,
                github_path="",
                cron_output_path=str(path),
                tags="cron-history,daily-schedule,investment-plan,crypto,etf",
            )
        )

    return rows


def existing_keys(worksheet) -> set[tuple[str, str, str, str]]:
    records = worksheet.get_all_records()
    keys = set()
    for record in records:
        keys.add(
            (
                str(record.get("date", "")),
                str(record.get("source", "")),
                str(record.get("github_path", "")),
                str(record.get("cron_output_path", "")),
            )
        )
    return keys


def main() -> None:
    worksheet = get_worksheet()
    seen = existing_keys(worksheet)
    rows = []
    for row in collect_rows():
        key = (row.date, row.source, row.github_path, row.cron_output_path)
        if key in seen:
            continue
        rows.append(row.as_sheet_row())

    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"Imported {len(rows)} new journal rows into worksheet {WORKSHEET}.")


if __name__ == "__main__":
    main()
