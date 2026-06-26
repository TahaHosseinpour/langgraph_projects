import os
import json
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

try:
    from graphs.prompt import (
        REVEAL_SYSTEM_PROMPT,
        CONTENT_SYSTEM_PROMPTS,
        build_content_request,
        build_design_prompt,
        build_html_prompt,
    )
except ImportError:
    from prompt import (
        REVEAL_SYSTEM_PROMPT,
        CONTENT_SYSTEM_PROMPTS,
        build_content_request,
        build_design_prompt,
        build_html_prompt,
    )

load_dotenv()


# ── State ──────────────────────────────────────────────────────────────────

class PresentationRequest(TypedDict):
    topic:            str
    audience:         str
    num_slides:       int
    tone:             str
    user_preferences: str

class ColorPalette(TypedDict):
    primary_bg:    str
    secondary_bg:  str
    accent:        str
    text_primary:  str
    text_secondary: str

class Typography(TypedDict):
    font_family:    str
    heading_size:   int
    body_size:      int
    weight_heading: int
    weight_body:    int

class DesignSystem(TypedDict):
    colors:       ColorPalette
    typography:   Typography
    layout_style: str

class Slide(TypedDict):
    index:       int
    title:       str
    content:     list[str]
    layout_hint: str

class PresentationState(TypedDict):
    request:       PresentationRequest
    design_system: DesignSystem
    slides:        list[Slide]
    html_code:     str
    approved:      bool
    messages:      Annotated[list, add_messages]


# ── LLMs ───────────────────────────────────────────────────────────────────

_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
_key  = os.getenv("OPENAI_API_KEY")

llm_content = ChatOpenAI(model=os.getenv("OPENAI_MODEL_CONTENT", "gpt-4o-mini"), base_url=_base, api_key=_key, temperature=0.7)
llm_design  = ChatOpenAI(model=os.getenv("OPENAI_MODEL_DESIGN",  "gpt-4o-mini"), base_url=_base, api_key=_key, temperature=0.5)
llm_html    = ChatOpenAI(model=os.getenv("OPENAI_MODEL_JSX",     "gpt-4o-mini"), base_url=_base, api_key=_key, temperature=0.7)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text.strip())


# ── Nodes ──────────────────────────────────────────────────────────────────

def generate_design(state: PresentationState) -> dict:
    req      = state["request"]
    response = llm_design.invoke([HumanMessage(content=build_design_prompt(req))])
    return {"design_system": _parse_json(response.content)}


def _generate_content(state: PresentationState, tone_key: str) -> dict:
    """Shared body — each content node feeds its own tone's SYSTEM prompt."""
    req      = state["request"]
    response = llm_content.invoke([
        SystemMessage(content=CONTENT_SYSTEM_PROMPTS[tone_key]),
        HumanMessage(content=build_content_request(req)),
    ])
    slides   = _parse_json(response.content)
    return {
        "slides":   slides,
        "messages": [AIMessage(content=f"[{tone_key} path] Content ready: {len(slides)} slides")],
    }


def generate_content_technical(state: PresentationState) -> dict:
    return _generate_content(state, "technical")


def generate_content_formal(state: PresentationState) -> dict:
    return _generate_content(state, "formal")


def generate_content_casual(state: PresentationState) -> dict:
    return _generate_content(state, "casual")


def assemble_outline(state: PresentationState) -> dict:
    colors    = state["design_system"]["colors"]
    assembled = []
    for slide in state["slides"]:
        is_accent = slide["layout_hint"] == "hero" or slide["index"] % 5 == 0
        assembled.append({
            **slide,
            "bg_color": colors["secondary_bg"] if is_accent else colors["primary_bg"],
        })
    return {"slides": assembled}


def generate_html(state: PresentationState) -> dict:
    response = llm_html.invoke([
        SystemMessage(content=REVEAL_SYSTEM_PROMPT),
        HumanMessage(content=build_html_prompt(
            state["request"], state["design_system"], state["slides"]
        )),
    ])
    html = response.content.strip()
    if html.startswith("```"):
        lines = html.split("\n")
        html  = "\n".join(lines[1:-1]).strip()
    return {
        "html_code": html,
        "messages":  [AIMessage(content="Reveal.js HTML generated.")],
    }


def validate_html(state: PresentationState) -> dict:
    html = state.get("html_code", "")
    if "reveal.js" not in html:
        raise ValueError("Missing reveal.js CDN — generation failed")
    if "<section" not in html:
        raise ValueError("Missing slide sections")
    if len(html) < 500:
        raise ValueError("HTML too short — generation likely failed")
    return {}


# ── Conditional Router ──────────────────────────────────────────────────────

# Map each tone to exactly one content node. The router returns a single node
# name (a string), so only ONE of the three content nodes ever runs.
_TONE_TO_NODE = {
    "technical": "generate_content_technical",
    "formal":    "generate_content_formal",
    "casual":    "generate_content_casual",
}


def route_by_tone(state: PresentationState) -> str:
    tone = state["request"]["tone"]
    return _TONE_TO_NODE.get(tone, "generate_content_formal")


# ── Graph ──────────────────────────────────────────────────────────────────

def create_graph():
    builder = StateGraph(PresentationState)

    builder.add_node("generate_design",            generate_design)
    builder.add_node("generate_content_technical", generate_content_technical)
    builder.add_node("generate_content_formal",    generate_content_formal)
    builder.add_node("generate_content_casual",    generate_content_casual)
    builder.add_node("assemble_outline",           assemble_outline)
    builder.add_node("generate_html",              generate_html)
    builder.add_node("validate_html",              validate_html)

    # Design runs first (sequential, no longer parallel with content).
    builder.add_edge(START, "generate_design")

    # Then route to exactly ONE content node based on tone.
    builder.add_conditional_edges(
        "generate_design",
        route_by_tone,
        ["generate_content_technical", "generate_content_formal", "generate_content_casual"],
    )

    # All three content branches converge back to the linear tail.
    builder.add_edge("generate_content_technical", "assemble_outline")
    builder.add_edge("generate_content_formal",    "assemble_outline")
    builder.add_edge("generate_content_casual",    "assemble_outline")
    builder.add_edge("assemble_outline",           "generate_html")
    builder.add_edge("generate_html",              "validate_html")
    builder.add_edge("validate_html",              END)

    return builder.compile()
