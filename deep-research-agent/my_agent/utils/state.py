"""State definitions for the deep research agent."""

import operator
from typing import Annotated, TypedDict


class SearchResult(TypedDict):
    """A single search result returned by the search tool."""

    query: str  # The query that produced this result
    content: str  # Concatenated snippets returned by the search engine


class ResearchState(TypedDict):
    """Main state shared across the whole research workflow."""

    # Input
    topic: str  # The research topic provided by the user

    # Planning phase
    research_plan: str  # High-level plan produced by the planner
    search_queries: list[str]  # Concrete queries to run next

    # Search phase (reducer because results accumulate across loops)
    search_results: Annotated[list[SearchResult], operator.add]

    # Synthesis phase
    findings: str  # Condensed findings extracted from the results

    # Writing phase
    final_report: str  # The final markdown report

    # Control flow
    iteration_count: int  # How many research loops we have run
    max_iterations: int  # Maximum number of loops allowed
