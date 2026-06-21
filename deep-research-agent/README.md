# Deep Research Agent

A simplified deep research agent built with LangGraph, inspired by
[open_deep_research](https://github.com/langchain-ai/open_deep_research).

## Flow

```
plan_research -> run_search -> synthesize -> (refine_queries -> run_search)* -> write_report
```

1. **plan_research** – turns the topic into a plan and 3 search queries.
2. **run_search** – runs web search (Tavily) for each query.
3. **synthesize** – condenses the results into findings and notes gaps.
4. **refine_queries** – generates follow-up queries while iterations remain.
5. **write_report** – writes the final markdown report.

## Run

```bash
pip install -r requirements.txt
# fill in OPENAI_API_KEY, OPENAI_BASE_URL and TAVILY_API_KEY in .env
langgraph dev
```

### Example input

```json
{
  "topic": "The impact of LangGraph on agent development",
  "max_iterations": 1
}
```
