"""Graph assembly for the Automated Job Tailoring workflow.

Topology:
    START -> selector -> writer -> critic
        -> [score >= 85 or iterations >= 3 ? cover_letter -> END : writer]
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents import (
    ats_critic_node,
    cover_letter_node,
    project_picker_node,
    resume_selector_node,
    resume_writer_node,
    scrubber_node,
)
from state import ATS_SCORE_THRESHOLD, MAX_ITERATIONS, TailoringState


def route_on_score(state: TailoringState) -> Literal["writer", "cover_letter"]:
    """Decide whether to accept the resume or loop back for revision.

    Terminates when the ATS score meets the threshold or the iteration
    cap is reached, preventing unbounded API usage.
    """
    if state["ats_score"] >= ATS_SCORE_THRESHOLD:
        print(
            f"[router] Score {state['ats_score']} >= {ATS_SCORE_THRESHOLD} "
            "— target achieved. Writing cover letter."
        )
        return "cover_letter"
    if state["iteration_count"] >= MAX_ITERATIONS:
        print(
            f"[router] Iteration cap ({MAX_ITERATIONS}) reached with score "
            f"{state['ats_score']}. Writing cover letter with best effort."
        )
        return "cover_letter"
    print(
        f"[router] Score {state['ats_score']} < {ATS_SCORE_THRESHOLD} "
        f"(iteration {state['iteration_count']}/{MAX_ITERATIONS}) "
        "— routing feedback back to writer."
    )
    return "writer"


def build_graph():
    """Assemble and compile the tailoring StateGraph."""
    workflow = StateGraph(TailoringState)

    workflow.add_node("selector", resume_selector_node)
    workflow.add_node("project_picker", project_picker_node)
    workflow.add_node("writer", resume_writer_node)
    workflow.add_node("critic", ats_critic_node)
    workflow.add_node("scrubber", scrubber_node)
    workflow.add_node("cover_letter", cover_letter_node)

    workflow.add_edge(START, "selector")
    workflow.add_edge("selector", "project_picker")
    workflow.add_edge("project_picker", "writer")
    workflow.add_edge("writer", "critic")
    workflow.add_conditional_edges(
        "critic",
        route_on_score,
        {"writer": "writer", "cover_letter": "scrubber"},
    )
    workflow.add_edge("scrubber", "cover_letter")
    workflow.add_edge("cover_letter", END)

    return workflow.compile()


app = build_graph()
