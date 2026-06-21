"""Build the data analysis agent graph.

Flow:
    generate_hypothesis -> analyze_data -> (retry on error)* -> write_report
"""

from langgraph.graph import END, START, StateGraph

from my_agent.utils.nodes import (
    analyze_data,
    generate_hypothesis,
    should_reanalyze,
    write_report,
)
from my_agent.utils.state import DataAnalysisState


def build_graph():
    """Construct and compile the data analysis workflow graph."""
    workflow = StateGraph(DataAnalysisState)

    # Register nodes (one per agent role).
    workflow.add_node("generate_hypothesis", generate_hypothesis)
    workflow.add_node("analyze_data", analyze_data)
    workflow.add_node("write_report", write_report)

    # Wire the flow.
    workflow.add_edge(START, "generate_hypothesis")
    workflow.add_edge("generate_hypothesis", "analyze_data")

    # Retry the analysis on error, otherwise move on to the report.
    workflow.add_conditional_edges(
        "analyze_data",
        should_reanalyze,
        {"retry": "analyze_data", "report": "write_report"},
    )
    workflow.add_edge("write_report", END)

    return workflow.compile()


# Exposed graph used by langgraph.json for deployment.
graph = build_graph()
