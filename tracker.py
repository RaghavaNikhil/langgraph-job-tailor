"""Logs each tailoring run to a local CSV application tracker."""

import csv
from datetime import datetime
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "applications.csv"
PENDING_FILE = TRACKER_FILE.with_stem(TRACKER_FILE.stem + "_pending")

COLUMNS = [
    "date", "company", "role", "status", "ats_score", "resume_version",
    "resume_file", "cover_letter_file", "job_url", "notes",
]


def _append_row(path: Path, row: list) -> None:
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(COLUMNS)
        writer.writerow(row)


def log_application(
    company: str,
    role: str,
    ats_score,
    resume_version: str,
    resume_file: str,
    cover_letter_file: str,
    job_url: str = "",
    status: str = "completed",
    notes: str = "",
) -> Path:
    """Append one run to applications.csv (created with headers if new).

    status is "completed" for a normal run, or "blocked" when the
    Eligibility Check short-circuited the graph before any resume was
    generated — ats_score/resume_file/cover_letter_file are blank then.

    If applications.csv is locked (e.g. open in Excel), the row is
    written to applications_pending.csv instead of crashing a run whose
    resume/cover letter already generated successfully — merge the
    pending rows in once the main file is free.
    """
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        company,
        role,
        status,
        ats_score,
        resume_version,
        resume_file,
        cover_letter_file,
        job_url,
        notes,
    ]
    try:
        _append_row(TRACKER_FILE, row)
        return TRACKER_FILE
    except PermissionError:
        _append_row(PENDING_FILE, row)
        print(
            f"[tracker] {TRACKER_FILE.name} is locked (probably open in "
            f"Excel). Logged to {PENDING_FILE.name} instead — merge its "
            "rows in once you close the file."
        )
        return PENDING_FILE
