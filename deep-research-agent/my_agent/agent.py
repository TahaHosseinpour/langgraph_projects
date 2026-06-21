"""Build the deep research agent graph.

Flow:
    plan_research -> run_search -> synthesize -> (refine -> run_search)* -> write_report
"""

from langgraph.graph import END, START, StateGraph

from my_agent.utils.nodes import (
    plan_research,
    refine_queries,
    run_search,
    should_continue,
    synthesize,
    write_report,
)
from my_agent.utils.state import ResearchState


def build_graph():
    """Construct and compile the research workflow graph."""
    workflow = StateGraph(ResearchState)

    # Register nodes.
    workflow.add_node("plan_research", plan_research)
    workflow.add_node("run_search", run_search)
    workflow.add_node("synthesize", synthesize)
    workflow.add_node("refine_queries", refine_queries)
    workflow.add_node("write_report", write_report)

    # Wire the linear part of the flow.
    workflow.add_edge(START, "plan_research")
    workflow.add_edge("plan_research", "run_search")
    workflow.add_edge("run_search", "synthesize")

    # After synthesis, either loop for more research or write the report.
    workflow.add_conditional_edges(
        "synthesize",
        should_continue,
        {"refine": "refine_queries", "write": "write_report"},
    )
    workflow.add_edge("refine_queries", "run_search")
    workflow.add_edge("write_report", END)

    return workflow.compile()


# Exposed graph used by langgraph.json for deployment.
graph = build_graph()
