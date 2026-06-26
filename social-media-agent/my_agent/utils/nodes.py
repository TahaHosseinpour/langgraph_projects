"""Node functions for the social media agent."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Send, interrupt

from my_agent.utils.state import GeneratePostState, VerifyState
from my_agent.utils.tools import fetch_url

# Maximum allowed length for a single post (e.g. the X/Twitter limit).
MAX_POST_LENGTH = 280
# Maximum number of times we try to shorten an over-long post.
MAX_CONDENSE_ATTEMPTS = 3

# base_url is read from OPENAI_BASE_URL so a custom/compatible endpoint can be used.
model = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0.3,
    base_url=os.getenv("OPENAI_BASE_URL"),
)


def fanout_links(state: GeneratePostState) -> list[Send]:
    """Fan out: send each link to its own parallel verifier branch."""
    return [Send("verify_link", {"url": url}) for url in state["links"]]


def verify_link(state: VerifyState) -> dict:
    """Fetch and verify the content behind a single link."""
    content = fetch_url.invoke({"url": state["url"]})
    return {"verified_urls": [{"url": state["url"], "content": content}]}


def init_flow(state: GeneratePostState) -> dict:
    """Reset per-run control fields before generation starts."""
    return {"condense_count": 0}


def generate_report(state: GeneratePostState) -> dict:
    """Generate a short marketing report from the verified content."""
    combined = "\n\n".join(
        f"URL: {item['url']}\n{item['content']}" for item in state["verified_urls"]
    )
    system = SystemMessage(
        content=(
            "You are a marketing analyst. Read the content below and write a "
            "short report (3-5 bullet points) describing what it is about and "
            "why it is interesting to a developer audience."
        )
    )
    response = model.invoke([system, HumanMessage(content=combined)])
    return {"report": response.text}


def generate_post(state: GeneratePostState) -> dict:
    """Generate a social media post from the marketing report."""
    system = SystemMessage(
        content=(
            "You are a social media manager. Write a single engaging post for "
            f"X/Twitter based on the report. Keep it under {MAX_POST_LENGTH} "
            "characters, friendly and concise. Avoid hashtag spam."
        )
    )
    response = model.invoke([system, HumanMessage(content=state["report"])])
    return {"post": response.text.strip()}


def condense_post(state: GeneratePostState) -> dict:
    """Shorten the post when it exceeds the maximum length."""
    system = SystemMessage(
        content=(
            f"The following post is too long. Rewrite it to be under "
            f"{MAX_POST_LENGTH} characters while keeping the key message."
        )
    )
    response = model.invoke([system, HumanMessage(content=state["post"])])
    return {
        "post": response.text.strip(),
        "condense_count": state.get("condense_count", 0) + 1,
    }


def human_review(state: GeneratePostState) -> dict:
    """Pause for a human to approve or edit the post before scheduling."""
    # interrupt() suspends the graph and surfaces this payload to the client.
    decision = interrupt(
        {
            "post": state["post"],
            "report": state["report"],
            "action": "Approve the post, or resume with an edited version.",
        }
    )
    # `decision` is provided when the graph is resumed with Command(resume=...).
    if isinstance(decision, dict) and decision.get("post"):
        return {"post": decision["post"]}
    return {}


def schedule_post(state: GeneratePostState) -> dict:
    """Schedule the approved post (mocked here)."""
    # In a real system this would call the Twitter/LinkedIn API.
    print(f"[scheduled] {state['post']}")
    return {}


def needs_condense(state: GeneratePostState) -> str:
    """Decide whether the post must be condensed further."""
    too_long = len(state.get("post", "")) > MAX_POST_LENGTH
    attempts_left = state.get("condense_count", 0) < MAX_CONDENSE_ATTEMPTS
    if too_long and attempts_left:
        return "condense"
    return "review"
