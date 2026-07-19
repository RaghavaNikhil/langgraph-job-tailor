"""State definitions for the Automated Job Tailoring graph."""

from typing import Dict, List, TypedDict


class TailoringState(TypedDict):
    """Shared state passed between nodes in the tailoring workflow.

    Attributes:
        job_description: The target job posting text.
        available_resumes: All candidate resume versions, name -> text.
        master_resume: Detailed master resume used as the fact bank the
            writer may draw real projects/details from (never sent to ATS
            directly).
        candidate_profile: Authoritative personal facts (work authorization,
            location, etc.) the writer must never contradict.
        selected_resume_name: Name of the version chosen by the Selector.
        base_resume: Text of the selected resume version (never mutated).
        tailored_resume: The latest rewrite produced by the Writer node.
        critic_feedback: Actionable feedback items from the ATS Critic.
        ats_score: Most recent ATS alignment score (0-100).
        iteration_count: Number of completed write->critique loops.
    """

    job_description: str
    job_company: str
    job_role: str
    available_resumes: Dict[str, str]
    master_resume: str
    candidate_profile: str
    selected_resume_name: str
    selected_projects: List[str]
    base_resume: str
    tailored_resume: str
    critic_feedback: List[str]
    ats_score: int
    best_resume: str
    best_score: int
    iteration_count: int
    cover_letter: str


MAX_ITERATIONS = 3
ATS_SCORE_THRESHOLD = 85
