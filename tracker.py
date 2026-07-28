"""Logs each tailoring run to a local CSV application tracker."""

import csv
from datetime import datetime
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "applications.csv"

COLUMNS = [
    "date", "company", "role", "status", "ats_score", "resume_version",
    "resume_file", "cover_letter_file", "job_url", "notes",
]


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
    """
    is_new = not TRACKER_FILE.exists()
    with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(COLUMNS)
        writer.writerow([
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
        ])
    return TRACKER_FILE
