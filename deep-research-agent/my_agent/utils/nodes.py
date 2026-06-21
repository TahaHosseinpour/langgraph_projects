"""Node functions for the deep research agent."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from my_agent.utils.state import ResearchState, SearchResult
from my_agent.utils.tools import web_search

# Shared model instance used by every node.
# base_url is read from OPENAI_BASE_URL so a custom/compatible endpoint can be used.
model = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    base_url=os.getenv("OPENAI_BASE_URL"),
)


def plan_research(state: ResearchState) -> dict:
    """Create a research plan and an initial list of search queries."""
    system = SystemMessage(
        content=(
            "You are a research planner. Given a topic, write a short research "
            "plan (2-3 sentences) and then list 3 focused web search queries. "
            "Return the plan first, then a line containing only '---', then one "
            "query per line."
        )
    )
    response = model.invoke([system, HumanMessage(content=f"Topic: {state['topic']}")])
    text = response.text()

    # Split the plan from the queries on the '---' separator.
    plan, _, queries_block = text.partition("---")
    queries = [
        line.strip("- ").strip()
        for line in queries_block.strip().splitlines()
        if line.strip()
    ]
    return {
        "research_plan": plan.strip(),
        "search_queries": queries[:3] or [state["topic"]],
        "iteration_count": 0,
    }


def run_search(state: ResearchState) -> dict:
    """Run web search for each planned query and collect the results."""
    results: list[SearchResult] = []
    for query in state["search_queries"]:
        content = web_search.invoke({"query": query})
        results.append({"query": query, "content": content})
    return {"search_results": results}


def synthesize(state: ResearchState) -> dict:
    """Summarize the collected search results into findings."""
    combined = "\n\n".join(
        f"Query: {r['query']}\n{r['content']}" for r in state["search_results"]
    )
    system = SystemMessage(
        content=(
            "You are a research analyst. Summarize the search results below into "
            "clear, factual findings about the topic. Explicitly note any gaps "
            "that still need more research."
        )
    )
    response = model.invoke(
        [system, HumanMessage(content=f"Topic: {state['topic']}\n\nResults:\n{combined}")]
    )
    return {
        "findings": response.text(),
        "iteration_count": state["iteration_count"] + 1,
    }


def refine_queries(state: ResearchState) -> dict:
    """Generate follow-up queries based on the gaps in the current findings."""
    system = SystemMessage(
        content=(
            "Based on the current findings, list up to 2 follow-up web search "
            "queries that would fill the remaining gaps. One query per line."
        )
    )
    response = model.invoke(
        [
            system,
            HumanMessage(
                content=f"Topic: {state['topic']}\n\nFindings:\n{state['findings']}"
            ),
        ]
    )
    queries = [
        line.strip("- ").strip()
        for line in response.text().splitlines()
        if line.strip()
    ]
    return {"search_queries": queries[:2] or [state["topic"]]}


def write_report(state: ResearchState) -> dict:
    """Write the final research report from the accumulated findings."""
    system = SystemMessage(
        content=(
            "You are a technical writer. Write a well-structured markdown report "
            "on the topic using the findings. Include a title, an overview, key "
            "sections, and a short conclusion."
        )
    )
    response = model.invoke(
        [
            system,
            HumanMessage(
                content=f"Topic: {state['topic']}\n\nFindings:\n{state['findings']}"
            ),
        ]
    )
    return {"final_report": response.text()}


def should_continue(state: ResearchState) -> str:
    """Decide whether to run another research loop or write the report."""
    if state["iteration_count"] < state["max_iterations"]:
        return "refine"
    return "write"
