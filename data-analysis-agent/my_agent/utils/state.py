"""State definitions for the data analysis agent."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class DataAnalysisState(TypedDict):
    """Main state for the data analysis workflow."""

    # Input
    data_path: str  # Path to the CSV file to analyze
    question: str  # The analytical question from the user

    # Conversation/log shared between the agents (add_messages appends)
    messages: Annotated[list[AnyMessage], add_messages]

    # Hypothesis phase
    hypothesis: str  # Hypothesis generated about the data

    # Analysis phase
    analysis_code: str  # Latest python code produced by the analyzer
    # Reducer because each analysis attempt appends a new result
    analysis_result: Annotated[list[str], operator.add]

    # Reporting phase
    report: str  # Final markdown report

    # Control flow
    iteration_count: int  # How many analysis attempts we have made
    max_iterations: int  # Maximum number of attempts allowed
