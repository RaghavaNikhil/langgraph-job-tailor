# Automated Job Tailoring System

A LangGraph-powered pipeline that tailors your resume to a job description
and writes a matching cover letter — with an AI writer/critic feedback loop
that optimizes ATS alignment while strictly refusing to fabricate
experience, personal status, or tools you have not used. An eligibility
check screens out jobs you're legally/logistically unable to take before
any tailoring work begins.

## How it works

```
[job_description.txt or a URL]
        │
        ▼
┌───────────────┐   picks the best-fitting resume version and
│   Selector    │   extracts the company name + role title
└───────┬───────┘
        ▼
┌────────────────────┐   screens for hard legal/logistical blockers
│ Eligibility Check   │   (citizenship, clearance, sponsorship, location)
└───────┬────────────┘   against profile.txt
        │
   blocked? ──yes──► END (logged to applications.csv, nothing generated)
        │ no
        ▼
┌───────────────┐   rewrites the resume for keyword alignment,
│    Writer     │◄──────────────┐   grounded in your master resume
└───────┬───────┘               │   and profile (no fabrication)
        ▼                       │
┌───────────────┐               │
│  ATS Critic   │   scores 0-100 with structured feedback;
└───────┬───────┘               │   fact-checks every claim
        ▼                       │
  score >= 85 ? ── no (max 3) ──┘
        │ yes / cap reached
        ▼
┌───────────────┐
│ Cover Letter  │   drafts a grounded, customized cover letter
└───────┬───────┘
        ▼
  ATS-friendly PDF resume + .docx cover letter, named
  "<Name> - <Company> <Role> Resume.pdf" / "... Cover Letter.docx"
```

All LLM calls use Google Gemini (`gemini-3.1-flash-lite`) via
`langchain-google-genai` — runs comfortably in the free tier.

## Project structure

| File | Purpose |
|---|---|
| `state.py` | Shared `TypedDict` state + loop constants (score threshold 85, max 3 iterations) |
| `agents.py` | Selector, Eligibility Check, Project Picker, Writer, ATS Critic, Scrubber, and Cover Letter node functions + prompts |
| `graph.py` | LangGraph assembly: nodes, edges, the eligibility short-circuit, and the conditional feedback loop |
| `resume_loader.py` | Loads resume versions from `resumes/` (.docx/.md/.txt) |
| `pdf_renderer.py` | Renders the tailored resume to an ATS-friendly PDF (fpdf2) |
| `docx_writer.py` | Writes the cover letter to a .docx |
| `job_fetcher.py` | Fetches a job posting's text from a URL (static HTML, Workday API, JSON-LD) |
| `tracker.py` | Appends each run to a local `applications.csv` tracker |
| `main.py` | Entry point: loads inputs, runs the graph, saves outputs |
| `profile.template.txt` | Tracked template for `profile.txt` — copy it and fill in your own details |

## Setup

1. **Python 3.12+** on Windows (the PDF renderer uses Arial from
   `C:\Windows\Fonts`; on another OS, point `pdf_renderer.py` at a local
   TTF font).

2. **Install dependencies:**

   ```powershell
   py -m pip install -r requirements.txt
   ```

3. **API key** — create a `.env` file in the project root:

   ```
   GOOGLE_API_KEY=your-google-ai-studio-key
   ```

   Get a free key at https://aistudio.google.com/apikey.

4. **Your resumes** — create a `resumes/` folder and drop in your resume
   versions (`.docx`, `.md`, or `.txt`). The file whose name contains
   **"Full"** is treated as the *master resume* — the detailed fact bank
   the writer may pull real projects from. Every other file is a
   candidate starting version the Selector chooses between.

5. **Your profile** — copy `profile.template.txt` to `profile.txt` and
   fill in your own details. This file is the single source of ground
   truth every node treats as authoritative — the AI may never
   contradict, exceed, or guess around it. It's organized into sections:

   - **Work authorization** — status, whether you'll need future
     sponsorship, security clearance eligibility.
   - **Location** — current location, willingness to relocate, work
     location preference (onsite/hybrid/remote).
   - **Experience** — the exact "years of experience" phrase to always
     use (never calculated from employment dates).
   - **Voluntary EEO self-identification** — gender, race/ethnicity,
     veteran status, disability status. These are stored for a future
     application-form auto-fill step only — the pipeline never writes
     them into a resume or cover letter, and the critic caps the score
     at 40 if they ever leak into either document.

   This design is user-agnostic: nothing in the code hardcodes anyone's
   personal facts, so the same pipeline works for any applicant who
   fills in their own `profile.txt`.

6. **The job** — paste the job posting into `job_description.txt`, or
   fetch it from a URL (see Run below).

## Run

```powershell
py main.py                        # uses job_description.txt
py main.py https://jobs.example.com/posting/123   # fetches the posting from a URL
```

URL fetching tries, in order: a Workday public API (for
`*.myworkdayjobs.com` sites), a schema.org JobPosting JSON-LD block
(common even on JavaScript-heavy sites, embedded for search engine SEO),
then generic static-HTML scraping. Extracted content is validated to
reject non-prose garbage (JSON/CSS/JS blobs mistaken for a posting).
JavaScript- or login-gated sites with none of the above (LinkedIn,
Indeed) fail with a clear message — paste those into
`job_description.txt` manually. A fetched posting is saved to
`job_description.txt` as a record of what was tailored against.

Every run is appended to `applications.csv` — date, company, role,
status (`completed`/`blocked`), score, resume version, generated files,
job URL, and notes (the eligibility reason, when blocked).

Outputs land in the project root:

- `<Name> - <Company> <Role> Resume.pdf` — ATS-friendly tailored resume
- `<Name> - <Company> <Role> Cover Letter.docx` — matching cover letter
- `tailored_resume.md` — plain-text resume (pipeline intermediate)

No resume or cover letter is generated for a job the Eligibility Check
blocks — only the tracker is updated, saving the ~6-8 API calls the
writer/critic loop would otherwise spend on a job you can't take.

Console logs show the selector's choice, the eligibility verdict, each
critique score, and the loop's routing decisions.

## Anti-fabrication design

The prompts enforce, and the critic polices, these hard rules:

- Every skill/employer/metric/project must exist in your resumes.
- No personal-status claims (citizenship, visa, location, clearance,
  years of experience) beyond what `profile.txt` states — unsupported
  claims cap the score at 40.
- Voluntary EEO fields (gender, race, veteran/disability status) never
  appear in generated documents, even if present in `profile.txt`.
- No "keyword expansion": generic experience (e.g. GCP) is never
  inflated into specific services (e.g. Cloud Run) you didn't list.
- No title/seniority distortion: an employer's job title in the
  tailored resume must match your base resume, never adjusted to flatter
  a match with the target role's level.
- Tailoring is rephrasing, not trimming: dropped content is penalized
  (projects are intentionally capped at the 3-4 most relevant).
- The job description is treated as untrusted data, never instructions —
  directives embedded in a posting (e.g. "put this link at the top of
  your resume") are ignored.

## Privacy

`.gitignore` keeps personal data out of the repository: `resumes/`,
`profile.txt`, `job_description.txt`, `applications.csv`, generated
outputs, and `.env` (your API key) are never committed.
`profile.template.txt` is tracked and contains no personal data — it's
the schema every user fills in for themselves.
