# Data Analysis Multi-Agent

A simplified multi-agent data analysis system built with LangGraph, inspired by
[AI-Data-Analysis-MultiAgent](https://github.com/aimped-ai/ai-data-analysis-MultiAgent).

## Flow

```
generate_hypothesis -> analyze_data -> (retry on error, max N)* -> write_report
```

Each node plays a distinct agent role:

1. **generate_hypothesis** – inspects the data and proposes a testable hypothesis.
2. **analyze_data** – writes pandas code and runs it via the `run_python` tool;
   on failure it self-corrects using the captured error.
3. **write_report** – summarizes the findings into a markdown report.

## Run

```bash
pip install -r requirements.txt
# fill in OPENAI_API_KEY and OPENAI_BASE_URL in .env
langgraph dev
```

### Example input

```json
{
  "data_path": "data/sales.csv",
  "question": "Is there a relationship between price and units sold?",
  "max_iterations": 2
}
```

> Note: `run_python` executes model-generated code with `exec`. It is intended
> for local, trusted analysis only — do not expose it to untrusted input.
