"""Entry point for the Automated Job Tailoring workflow.

Loads the API key, reads all resume versions from `resumes/`, reads the
target job description from `job_description.txt` (falls back to a built-in
sample), runs the select->write->critique loop, and saves the result.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder before anything needs the key

from docx_writer import write_cover_letter_docx
from graph import app
from job_fetcher import FetchError, fetch_job_description
from tracker import log_application
from pdf_renderer import render_pdf
from resume_loader import load_resumes
from state import TailoringState

PROJECT_DIR = Path(__file__).parent
JOB_DESCRIPTION_FILE = PROJECT_DIR / "job_description.txt"
PROFILE_FILE = PROJECT_DIR / "profile.txt"
OUTPUT_FILE = PROJECT_DIR / "tailored_resume.md"


def safe_filename(text: str) -> str:
    """Strip characters Windows does not allow in filenames."""
    return re.sub(r'[<>:"/\\|?*]', "", text).strip()

SAMPLE_JOB_DESCRIPTION = """\
Senior Software Engineer (Python / AI) — CloudScale Systems

We are seeking a Senior Software Engineer to build LLM-powered products.

Responsibilities:
- Design and ship backend services in Python powering AI features.
- Build agentic workflows and RAG pipelines using LangChain / LangGraph.
- Deploy and operate services on cloud infrastructure with CI/CD.
- Collaborate with product teams to deliver reliable, tested features.

Requirements:
- 3+ years of software engineering experience with strong Python.
- Hands-on experience with LLM APIs, prompt engineering, and vector search.
- Experience with cloud platforms (GCP or AWS), Docker, and CI/CD.
- Strong grasp of testing, code review, and production observability.
"""


def ensure_api_key() -> None:
    """Verify GOOGLE_API_KEY is available before invoking the graph."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key or key == "PASTE_YOUR_KEY_HERE":
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Open the .env file in this folder "
            "and replace PASTE_YOUR_KEY_HERE with your real API key."
        )


EXCLUDED_SECTIONS = re.compile(
    r"\b(ADDITIONAL|ACADEMIC|OTHER|EXTRACURRICULAR|VOLUNTEER|LEADERSHIP)\b"
    r".*\b(EXPERIENCE|ACTIVITIES)\b",
    re.I,
)


def strip_excluded_sections(resume_text: str) -> str:
    """Remove non-professional sections (header through next all-caps header)."""
    kept, skipping = [], False
    for line in resume_text.splitlines():
        stripped = line.strip()
        is_header = (
            2 < len(stripped) < 60
            and any(c.isalpha() for c in stripped)
            and all(c.isupper() for c in stripped if c.isalpha())
        )
        if is_header:
            skipping = bool(EXCLUDED_SECTIONS.search(stripped))
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


EXCLUDED_ROLES = re.compile(
    r"graduate service assistant|instructional assistant|teaching assistant"
    r"|grader|food service|photography coordinator",
    re.I,
)


def strip_excluded_roles(resume_text: str) -> str:
    """Remove excluded role entries: the role line plus its bullet lines."""
    kept, skipping = [], False
    for line in resume_text.splitlines():
        stripped = line.strip()
        is_bullet = stripped.startswith(("-", "*", "•"))
        if not is_bullet and stripped:
            skipping = bool(EXCLUDED_ROLES.search(stripped))
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def load_job_description(url: str = "") -> str:
    """Get the job description: from a URL if given, else from file.

    A fetched posting is also written to job_description.txt so there is
    a local record of exactly what was tailored against.
    """
    if url:
        print(f"Fetching job posting from {url} ...")
        try:
            text = fetch_job_description(url)
        except FetchError as exc:
            raise SystemExit(f"\n{exc}") from exc
        JOB_DESCRIPTION_FILE.write_text(text, encoding="utf-8")
        print(f"Fetched {len(text)} chars; saved to {JOB_DESCRIPTION_FILE.name}")
        return text
    if JOB_DESCRIPTION_FILE.is_file():
        text = JOB_DESCRIPTION_FILE.read_text(encoding="utf-8").strip()
        if text:
            print(f"Loaded job description from {JOB_DESCRIPTION_FILE.name}")
            return text
    print("No job_description.txt found — using built-in sample JD.")
    return SAMPLE_JOB_DESCRIPTION


def main() -> None:
    ensure_api_key()

    job_url = ""
    if len(sys.argv) > 1:
        if sys.argv[1].startswith(("http://", "https://")):
            job_url = sys.argv[1]
        else:
            raise SystemExit(
                f"Unrecognized argument: {sys.argv[1]}\n"
                "Usage: py main.py [job_posting_url]"
            )

    candidates, master = load_resumes()
    print(f"Loaded {len(candidates)} resume versions: {list(candidates)}")
    print(f"Master resume {'loaded' if master else 'NOT found'} "
          f"({len(master)} chars)")

    profile = ""
    if PROFILE_FILE.is_file():
        profile = PROFILE_FILE.read_text(encoding="utf-8").strip()
    print(f"Candidate profile {'loaded' if profile else 'NOT found (profile.txt)'}")

    initial_state: TailoringState = {
        "job_description": load_job_description(job_url),
        "job_company": "",
        "job_role": "",
        "available_resumes": candidates,
        "master_resume": master,
        "candidate_profile": profile,
        "selected_resume_name": "",
        "eligibility_blocked": False,
        "eligibility_reason": "",
        "selected_projects": [],
        "base_resume": "",
        "tailored_resume": "",
        "critic_feedback": [],
        "ats_score": 0,
        "best_resume": "",
        "best_score": -1,
        "iteration_count": 0,
        "cover_letter": "",
    }

    print("=" * 70)
    print("Starting Automated Job Tailoring workflow")
    print("=" * 70)

    final_state = app.invoke(initial_state)

    company = final_state["job_company"] or "Company"
    role = final_state["job_role"] or "Role"

    if final_state["eligibility_blocked"]:
        print("\n" + "=" * 70)
        print("BLOCKED — not proceeding with this application")
        print(f"Company/Role: {company} / {role}")
        print(f"Reason: {final_state['eligibility_reason']}")
        print("=" * 70)
        tracker_path = log_application(
            company=company,
            role=role,
            ats_score="",
            resume_version=final_state["selected_resume_name"],
            resume_file="",
            cover_letter_file="",
            job_url=job_url,
            status="blocked",
            notes=final_state["eligibility_reason"],
        )
        print(f"Logged to tracker: {tracker_path.name}")
        return

    print("\n" + "=" * 70)
    print(f"SELECTED VERSION: {final_state['selected_resume_name']}")
    print(f"SHIPPED ATS SCORE: {max(final_state['best_score'], final_state['ats_score'])}")
    print(f"ITERATIONS USED : {final_state['iteration_count']}")
    print("=" * 70)

    resume_text = strip_excluded_sections(final_state["tailored_resume"])
    resume_text = strip_excluded_roles(resume_text)
    # Drop placeholder lines like "[INSERT VIDEO LINK HERE]" — artifacts of
    # instructions embedded in untrusted job descriptions.
    resume_text = "\n".join(
        l for l in resume_text.splitlines() if not re.fullmatch(r"\[.*\]", l.strip())
    ).lstrip("\n")
    OUTPUT_FILE.write_text(resume_text, encoding="utf-8")

    # Applicant name/contact come from the user's own base resume, not the
    # AI output, so untrusted JD content can never reach the filename.
    base_lines = [
        l.strip() for l in final_state["base_resume"].splitlines() if l.strip()
    ]
    applicant_name = base_lines[0] if base_lines else "Applicant"
    if applicant_name.isupper():
        applicant_name = applicant_name.title()
    contact_line = base_lines[1] if len(base_lines) > 1 else ""
    base_name = safe_filename(f"{applicant_name} - {company} {role}")

    pdf_path = render_pdf(resume_text, PROJECT_DIR / f"{base_name} Resume.pdf")
    print(f"\nTailored resume saved to: {OUTPUT_FILE.name} and {pdf_path.name}")

    docx_path = None
    if final_state["cover_letter"]:
        docx_path = write_cover_letter_docx(
            final_state["cover_letter"],
            PROJECT_DIR / f"{base_name} Cover Letter.docx",
            applicant_name,
            contact_line,
        )
        print(f"Cover letter saved to: {docx_path.name}")

    tracker_path = log_application(
        company=company,
        role=role,
        ats_score=max(final_state["best_score"], final_state["ats_score"]),
        resume_version=final_state["selected_resume_name"],
        resume_file=pdf_path.name,
        cover_letter_file=docx_path.name if docx_path else "",
        job_url=job_url,
    )
    print(f"Logged to tracker: {tracker_path.name}")

    print("\nTAILORED RESUME:\n")
    print(final_state["tailored_resume"])

    if final_state["critic_feedback"]:
        print("\nREMAINING CRITIC FEEDBACK:")
        for item in final_state["critic_feedback"]:
            print(f"- {item}")


if __name__ == "__main__":
    main()
