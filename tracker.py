"""Logs each tailoring run to a local CSV application tracker."""

import csv
from datetime import datetime
from pathlib import Path

TRACKER_FILE = Path(__file__).parent / "applications.csv"

COLUMNS = [
    "date", "company", "role", "ats_score", "resume_version",
    "resume_file", "cover_letter_file", "job_url",
]


def log_application(
    company: str,
    role: str,
    ats_score: int,
    resume_version: str,
    resume_file: str,
    cover_letter_file: str,
    job_url: str = "",
) -> Path:
    """Append one run to applications.csv (created with headers if new)."""
    is_new = not TRACKER_FILE.exists()
    with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(COLUMNS)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            company,
            role,
            ats_score,
            resume_version,
            resume_file,
            cover_letter_file,
            job_url,
        ])
    return TRACKER_FILE
