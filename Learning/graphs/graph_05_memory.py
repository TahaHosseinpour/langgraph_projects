import os
import json
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

try:
    from graphs.prompt import (
        REVEAL_SYSTEM_PROMPT,
        build_content_prompt,
        build_design_prompt,
        build_design_system_prompt,
        build_html_prompt,
    )
except ImportError:
    from prompt import (
        REVEAL_SYSTEM_PROMPT,
        build_content_prompt,
        build_design_prompt,
        build_design_system_prompt,
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
    request:           PresentationRequest
    design_system:     DesignSystem
    slides:            list[Slide]
    html_code:         str
    approved:          bool
    messages:          Annotated[list, add_messages]
    remembered_colors: dict   # color palette loaded from the Store at graph start


# ── LLMs ───────────────────────────────────────────────────────────────────

_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
_key  = os.getenv("OPENAI_API_KEY")

llm_content = ChatOpenAI(model=os.getenv("OPENAI_MODEL_CONTENT", "gpt-4o-mini"), base_url=_base, api_key=_key, temperature=0.7)
llm_design  = ChatOpenAI(model=os.getenv("OPENAI_MODEL_DESIGN",  "gpt-4o-mini"), base_url=_base, api_key=_key, temperature=0.5)
llm_html    = ChatOpenAI(model=os.getenv("OPENAI_MODEL_JSX",     "gpt-4o-mini"), base_url=_base, api_key=_key, temperature=0.7)

_USER_NS = ("user", "style_preferences")
_USER_ID = "default"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text.strip())


# ── Nodes ──────────────────────────────────────────────────────────────────

def generate_content(state: PresentationState) -> dict:
    req      = state["request"]
    response = llm_content.invoke([HumanMessage(content=build_content_prompt(req))])
    slides   = _parse_json(response.content)
    return {
        "slides":   slides,
        "messages": [AIMessage(content=f"Content ready: {len(slides)} slides")],
    }


def load_memory(state: PresentationState, store: BaseStore) -> dict:
    """First node: load the remembered color palette from the Store into state.
    Runs once per presentation, before content/design generation."""
    saved        = store.get(_USER_NS, _USER_ID)
    saved_colors = saved.value.get("colors") if saved else None
    return {"remembered_colors": saved_colors or {}}


def generate_design(state: PresentationState, store: BaseStore) -> dict:
    req = state["request"]

    # Remembered colors were loaded into state by load_memory. The design node's
    # SYSTEM prompt carries them and tells the model to reuse them when the user
    # gives no color preference — the model itself makes that call.
    remembered = state.get("remembered_colors") or None

    response = llm_design.invoke([
        SystemMessage(content=build_design_system_prompt(remembered)),
        HumanMessage(content=build_design_prompt(req)),
    ])
    design = _parse_json(response.content)

    # Remember this run's palette (+ style for the UI memory chip) for next time.
    store.put(_USER_NS, _USER_ID, {
        "font_family":  design["typography"]["font_family"],
        "layout_style": design["layout_style"],
        "accent":       design["colors"]["accent"],
        "colors":       design["colors"],
    })

    msg = "Reused your remembered color theme." if remembered else "Saved your color theme for next time."
    return {
        "design_system": design,
        "messages":      [AIMessage(content=msg)],
    }


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


# ── Graph ──────────────────────────────────────────────────────────────────

# Module-level so memories persist across multiple presentations in the same session.
store = InMemoryStore()

def create_graph():
    builder = StateGraph(PresentationState)

    builder.add_node("load_memory",      load_memory)
    builder.add_node("generate_content", generate_content)
    builder.add_node("generate_design",  generate_design)
    builder.add_node("assemble_outline", assemble_outline)
    builder.add_node("generate_html",    generate_html)
    builder.add_node("validate_html",    validate_html)

    # load_memory runs first → loads remembered colors into state, then content
    # and design generation fan out in parallel.
    builder.add_edge(START,              "load_memory")
    builder.add_edge("load_memory",      "generate_content")
    builder.add_edge("load_memory",      "generate_design")
    builder.add_edge("generate_content", "assemble_outline")
    builder.add_edge("generate_design",  "assemble_outline")
    builder.add_edge("assemble_outline", "generate_html")
    builder.add_edge("generate_html",    "validate_html")
    builder.add_edge("validate_html",    END)

    return builder.compile(store=store)
