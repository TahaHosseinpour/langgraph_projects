"""Build the social media agent graph.

Flow:
    START =(Send per link)=> verify_link -> init_flow -> generate_report
        -> generate_post -> (condense_post loop) -> human_review -> schedule_post
"""

from langgraph.graph import END, START, StateGraph

from my_agent.utils.nodes import (
    condense_post,
    fanout_links,
    generate_post,
    generate_report,
    human_review,
    init_flow,
    needs_condense,
    schedule_post,
    verify_link,
)
from my_agent.utils.state import GeneratePostState


def build_graph():
    """Construct and compile the post generation graph."""
    workflow = StateGraph(GeneratePostState)

    # Register nodes.
    workflow.add_node("verify_link", verify_link)
    workflow.add_node("init_flow", init_flow)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("generate_post", generate_post)
    workflow.add_node("condense_post", condense_post)
    workflow.add_node("human_review", human_review)
    workflow.add_node("schedule_post", schedule_post)

    # Fan out: one parallel verifier branch per link.
    workflow.add_conditional_edges(START, fanout_links, ["verify_link"])

    # All verifier branches join back here once finished.
    workflow.add_edge("verify_link", "init_flow")
    workflow.add_edge("init_flow", "generate_report")
    workflow.add_edge("generate_report", "generate_post")

    # Condense loop: shorten until the post fits or attempts run out.
    workflow.add_conditional_edges(
        "generate_post",
        needs_condense,
        {"condense": "condense_post", "review": "human_review"},
    )
    workflow.add_conditional_edges(
        "condense_post",
        needs_condense,
        {"condense": "condense_post", "review": "human_review"},
    )

    workflow.add_edge("human_review", "schedule_post")
    workflow.add_edge("schedule_post", END)

    # No checkpointer is passed here: when served via `langgraph dev`/Platform,
    # persistence (required by interrupt()) is provided automatically.
    return workflow.compile()


# Exposed graph used by langgraph.json for deployment.
graph = build_graph()
