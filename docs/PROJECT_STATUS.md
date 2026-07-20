# Project Journey: Automated Job Tailoring System

*Last updated: July 19, 2026 — active development branch: `phase-3-job-acquisition`*

---

## 1. The Vision (what we wished to do)

Build an automated job application assistant that:

1. Takes a job description and tailors a resume to it, optimizing ATS
   (Applicant Tracking System) keyword alignment — without lying.
2. Uses an AI feedback loop: a Writer drafts, a Critic scores, and the
   draft is revised until it is good enough (or a retry cap is hit).
3. Picks the best starting resume from a library of versions (Java,
   Python, LangChain, Regular) and enriches it from a detailed master
   resume.
4. Produces recruiter-ready artifacts: an ATS-friendly PDF resume and a
   customized cover letter, named per application.
5. Eventually: fetches postings itself, tracks applications, and
   automates more of the pipeline — with a human always reviewing before
   anything is submitted.

The original blueprint deliberately deferred browser automation (the
risky part) to the end, starting with the core text-refinement loop.

---

## 2. What We Built (what we did and how)

### Phase 1 — Core feedback loop ✅

The heart of the system, a LangGraph state machine:

```
START → selector → project_picker → writer → critic ─┬→ (score < 85, < 3 tries) → writer
                                                     └→ scrubber → cover_letter → END
```

- **`state.py`** — a `TypedDict` (`TailoringState`) that every node reads
  from and writes to: job description, resume versions, drafts, scores,
  feedback, iteration count.
- **Writer node** — Gemini (`gemini-3.1-flash-lite`) rewrites the resume
  for semantic keyword alignment with the job description.
- **ATS Critic node** — scores 0–100 with **structured output** (a
  Pydantic model, so the reply is guaranteed parseable JSON, never free
  text) and returns actionable feedback items.
- **Router** — plain Python conditional edge: score ≥ 85 → done;
  iterations ≥ 3 → done (cost cap); otherwise loop feedback back to the
  Writer.

### Phase 2a — Resume library & grounding ✅

- **`resume_loader.py`** — reads all `.docx`/`.md`/`.txt` files in
  `resumes/`; the file named "Full" becomes the *master resume* (fact
  bank), the rest are candidates.
- **Selector node** — picks the best starting version per job and
  extracts the company name + role title for file naming.
- **Project picker node** — pins the 4 most job-relevant projects once
  per run (temperature 0), so the writer can't reshuffle them between
  iterations.
- **`profile.txt`** — authoritative personal facts (work authorization,
  location) the AI may never contradict or exceed.

### Phase 2b — Output rendering ✅

- **`pdf_renderer.py`** — ATS-safe PDF: single column, real embedded
  Arial text, no tables/graphics; recovers visual structure from plain
  text (bold role lines with right-aligned dates, bold skill categories,
  two-row education layout, justified body text). Verified by extracting
  the text back out of the PDF.
- **`docx_writer.py`** — cover letter in .docx business-letter format.
- Files named `<Name> - <Company> <Role> Resume.pdf` / `...Cover
  Letter.docx`.

### Phase 3a — Job acquisition & tracking ✅ (current branch)

- **`job_fetcher.py`** — `py main.py <url>` fetches the posting text:
  static-HTML sites via scraping; **Workday** sites via their public
  CXS JSON API (their HTML is an empty JavaScript shell); clean error
  messages for login-gated sites (LinkedIn/Indeed).
- **`tracker.py`** — every run appends a row to `applications.csv`:
  date, company, role, score, files, URL.

### The hard-won lessons (defenses we had to build)

Every one of these was discovered by catching the AI misbehaving on a
real run:

| Incident | Defense built |
|---|---|
| Writer claimed **US citizenship** because the JD required it | `profile.txt` ground truth; zero-tolerance personal-status rules; critic caps score at 40 for violations |
| Writer copied the **job's location (Durham, NC)** into the resume header | Location/relocation added to the same zero-tolerance rules |
| Writer **dropped 40% of resume content** while "tailoring" | Completeness rules; critic penalizes omissions |
| Writer claimed **"Cloud Run, GKE, BigQuery"** experience from a generic "GCP" skill | Deterministic **scrubber**: code detects JD terms absent from source resumes; a temp-0 edit pass removes them |
| Writer **silently dropped skills** (FAISS, Pinecone, NumPy…) | Scrubber also token-diffs skills sections and restores anything missing |
| Final loop iteration scored **worse than an earlier draft** | Best-draft tracking: the highest-scoring draft is what ships |
| Writer obeyed an instruction **embedded in the job posting** ("put this link at the top of your resume") | JD declared untrusted data; filenames derive from the user's own files, never AI output; bracketed placeholders stripped in code |
| Unwanted sections/roles kept appearing (Grader, Photography Coordinator, "Academic and Other Experience") | Regex-based section and role strippers run on every output |

**The design principle that emerged:** prompts request behavior, but
only deterministic code guarantees it. Every guardrail that matters has
a code-level enforcement layer, with the LLM trusted only for judgment
and mechanical edits.

---

## 3. What Is Pending

### Phase 3 (remaining)

- **Batch mode** — process a folder/list of JDs in one run, each
  producing its own named outputs and tracker row.
- **Eligibility pre-check** — the selector already reads the JD; have it
  flag hard blockers (citizenship requirements, clearance, onsite-only
  vs. your location) *before* burning API calls, and record the verdict
  in the tracker.
- **Full browser automation** (deliberately last) — Playwright-driven
  fetching for JS-gated sites. Auto-*applying* is intentionally out of
  scope until there's a human-approval checkpoint: nothing should ever
  be submitted in your name without review.

### Quality & learning enhancements (optional, high value)

- **Human-in-the-loop checkpoint** — LangGraph `interrupt` support: pause
  after the critic loop for your approval/edits before rendering files.
- **Observability** — LangSmith tracing to inspect every prompt/response
  of every node (great for learning, too).
- **Score calibration** — the critic's 0–100 is a single LLM's opinion;
  averaging 2–3 critic calls or a rubric-based scorer would stabilize it.
- **Cover letter critique loop** — the resume gets a critic; the cover
  letter currently ships un-reviewed.
- **One-page enforcement** — measure rendered PDF length and have the
  writer tighten bullets if it spills past a page.

### Housekeeping

- Merge `phase-3-job-acquisition` → `master` once battle-tested.
- Unit tests (`pytest`) for the deterministic pieces: strippers,
  scrubber detection, education/role line parsers, Workday URL regex.
