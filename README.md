# Automated Job Tailoring System

A LangGraph-powered pipeline that tailors your resume to a job description
and writes a matching cover letter — with an AI writer/critic feedback loop
that optimizes ATS alignment while strictly refusing to fabricate
experience, personal status, or tools you have not used.

## How it works

```
[job_description.txt]
        │
        ▼
┌───────────────┐   picks the best-fitting resume version and
│   Selector    │   extracts the company name + role title
└───────┬───────┘
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
| `agents.py` | Selector, Writer, ATS Critic, and Cover Letter node functions + prompts |
| `graph.py` | LangGraph assembly: nodes, edges, and the conditional feedback loop |
| `resume_loader.py` | Loads resume versions from `resumes/` (.docx/.md/.txt) |
| `pdf_renderer.py` | Renders the tailored resume to an ATS-friendly PDF (fpdf2) |
| `docx_writer.py` | Writes the cover letter to a .docx |
| `job_fetcher.py` | Fetches a job posting's text from a URL (static-HTML sites) |
| `tracker.py` | Appends each run to a local `applications.csv` tracker |
| `main.py` | Entry point: loads inputs, runs the graph, saves outputs |

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

5. **Your profile** — create `profile.txt` with authoritative personal
   facts the AI must never contradict or exceed:

   ```
   Work authorization: <your real status>
   Location: <city, state>
   Willing to relocate: <yes/no>
   ```

6. **The job** — paste the job posting into `job_description.txt`.

## Run

```powershell
py main.py                        # uses job_description.txt
py main.py https://jobs.example.com/posting/123   # fetches the posting from a URL
```

URL fetching works for career sites that serve static HTML (Greenhouse,
Lever, most company sites). JavaScript- or login-gated sites (LinkedIn,
Indeed) fail with a clear message — paste those into
`job_description.txt` manually. A fetched posting is saved to
`job_description.txt` as a record of what was tailored against.

Every run is appended to `applications.csv` (date, company, role, score,
files) — your local application tracker.

Outputs land in the project root:

- `<Name> - <Company> <Role> Resume.pdf` — ATS-friendly tailored resume
- `<Name> - <Company> <Role> Cover Letter.docx` — matching cover letter
- `tailored_resume.md` — plain-text resume (pipeline intermediate)

Console logs show the selector's choice, each critique score, and the
loop's routing decisions.

## Anti-fabrication design

The prompts enforce, and the critic polices, these hard rules:

- Every skill/employer/metric/project must exist in your resumes.
- No personal-status claims (citizenship, visa, location, clearance)
  beyond what `profile.txt` states — unsupported claims cap the score at 40.
- No "keyword expansion": generic experience (e.g. GCP) is never
  inflated into specific services (e.g. Cloud Run) you didn't list.
- Tailoring is rephrasing, not trimming: dropped content is penalized
  (projects are intentionally capped at the 3-4 most relevant).

## Privacy

`.gitignore` keeps personal data out of the repository: `resumes/`,
`profile.txt`, `job_description.txt`, generated outputs, and `.env`
(your API key) are never committed.
