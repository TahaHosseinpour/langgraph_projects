"""Node functions for the deep research agent."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from my_agent.utils.state import ResearchState, SearchResult
from my_agent.utils.tools import web_search

# Shared model instance used by every node.
# base_url is read from OPENAI_BASE_URL so a custom/compatible endpoint can be used.
model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
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
    text = response.text

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
    """Update the running findings using the latest search results.

    Only the most recent batch of results is fed in (plus the prior findings)
    so the prompt does not grow without bound across loops.
    """
    recent = state["search_results"][-3:]
    combined = "\n\n".join(f"Query: {r['query']}\n{r['content']}" for r in recent)
    prior = state.get("findings", "")

    system = SystemMessage(
        content=(
            "You are a research analyst. Update the running findings using the "
            "new search results. Keep it factual and explicitly note any gaps "
            "that still need more research."
        )
    )
    try:
        response = model.invoke(
            [
                system,
                HumanMessage(
                    content=(
                        f"Topic: {state['topic']}\n\n"
                        f"Existing findings:\n{prior or '(none yet)'}\n\n"
                        f"New results:\n{combined}"
                    )
                ),
            ]
        )
        return {
            "findings": response.text,
            "iteration_count": state["iteration_count"] + 1,
        }
    except Exception as exc:  # noqa: BLE001 - stay fault-tolerant on model errors
        # If the model call fails, keep the findings we already have and stop
        # looping (by maxing out the counter) so write_report still runs.
        fallback = prior or f"Synthesis failed before any findings were collected: {exc}"
        return {
            "findings": fallback,
            "iteration_count": state.get("max_iterations", 1),
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
        for line in response.text.splitlines()
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
    return {"final_report": response.text}


def should_continue(state: ResearchState) -> str:
    """Decide whether to run another research loop or write the report."""
    max_iter = state.get("max_iterations", 1)
    if state.get("iteration_count", 0) < max_iter:
        return "refine"
    return "write"
