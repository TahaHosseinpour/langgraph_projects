"""Tools for the deep research agent."""

from langchain_core.tools import tool
from langchain_tavily import TavilySearch

# Single shared Tavily client. Requires TAVILY_API_KEY in the environment.
_search = TavilySearch(max_results=3)


@tool
def web_search(query: str) -> str:
    """Search the web for the given query and return concatenated snippets."""
    response = _search.invoke({"query": query})
    # TavilySearch returns a dict with a "results" list.
    chunks = []
    for item in response.get("results", []):
        chunks.append(
            f"{item.get('title', '')}\n"
            f"{item.get('content', '')}\n"
            f"{item.get('url', '')}"
        )
    return "\n\n".join(chunks) if chunks else "No results found."
