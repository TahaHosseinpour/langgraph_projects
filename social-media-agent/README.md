# Social Media Agent

A simplified social media post generator built with LangGraph, inspired by
[social-media-agent](https://github.com/langchain-ai/social-media-agent).

## Flow

```
START =(Send per link)=> verify_link -> init_flow -> generate_report
    -> generate_post -> (condense_post loop, max 3) -> human_review -> schedule_post
```

1. **verify_link** – each link is fetched in parallel via `Send` (map step).
2. **generate_report** – Claude writes a short marketing report.
3. **generate_post** – Claude drafts a post (< 280 chars).
4. **condense_post** – shortens the post if it is too long (up to 3 tries).
5. **human_review** – `interrupt()` pauses for human approval/editing.
6. **schedule_post** – schedules the approved post (mocked).

## Run

```bash
pip install -r requirements.txt
# fill in OPENAI_API_KEY and OPENAI_BASE_URL in .env
langgraph dev
```

### Example input

```json
{
  "links": ["https://github.com/langchain-ai/langgraph"]
}
```

### Resuming after human review

The graph pauses at `human_review`. Resume it with a `Command`:

```python
from langgraph.types import Command

# Approve as-is:
app.invoke(Command(resume={}), config)
# Or submit an edited post:
app.invoke(Command(resume={"post": "my edited post"}), config)
```
