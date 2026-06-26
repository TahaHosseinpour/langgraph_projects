import os
import json
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from dotenv import load_dotenv

try:
    from graphs.prompt import (
        REVEAL_SYSTEM_PROMPT,
        build_content_prompt,
        build_design_prompt,
        build_html_prompt,
    )
except ImportError:
    from prompt import (
        REVEAL_SYSTEM_PROMPT,
        build_content_prompt,
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

# streaming=True lets tokens flow through stream_mode="messages" in the caller
llm_html = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL_JSX", "gpt-4o-mini"),
    base_url=_base,
    api_key=_key,
    temperature=0.7,
    streaming=True,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text.strip())


# ── Nodes ──────────────────────────────────────────────────────────────────

def generate_content(state: PresentationState) -> dict:
    writer = get_stream_writer()
    writer({"node": "generate_content", "status": "running", "label": "Generating slide content..."})

    req      = state["request"]
    response = llm_content.invoke([HumanMessage(content=build_content_prompt(req))])
    slides   = _parse_json(response.content)

    writer({"node": "generate_content", "status": "done", "label": f"Content ready: {len(slides)} slides"})
    return {
        "slides":   slides,
        "messages": [AIMessage(content=f"Content ready: {len(slides)} slides for '{req['topic']}'")],
    }


def generate_design(state: PresentationState) -> dict:
    writer = get_stream_writer()
    writer({"node": "generate_design", "status": "running", "label": "Generating design system..."})

    req      = state["request"]
    response = llm_design.invoke([HumanMessage(content=build_design_prompt(req))])
    design   = _parse_json(response.content)

    writer({
        "node":   "generate_design",
        "status": "done",
        "label":  f"Design ready: {design['layout_style']} / {design['typography']['font_family']}",
    })
    return {"design_system": design}


def assemble_outline(state: PresentationState) -> dict:
    writer = get_stream_writer()
    writer({"node": "assemble_outline", "status": "running", "label": "Assembling outline..."})

    colors    = state["design_system"]["colors"]
    assembled = []
    for slide in state["slides"]:
        is_accent = slide["layout_hint"] == "hero" or slide["index"] % 5 == 0
        assembled.append({
            **slide,
            "bg_color": colors["secondary_bg"] if is_accent else colors["primary_bg"],
        })

    writer({"node": "assemble_outline", "status": "done", "label": "Outline assembled"})
    return {"slides": assembled}


def generate_html(state: PresentationState) -> dict:
    writer = get_stream_writer()
    writer({"node": "generate_html", "status": "running", "label": "Generating reveal.js HTML... (streaming)"})

    # With streaming=True and stream_mode="messages" in the caller,
    # tokens from this LLM call arrive incrementally through the SSE stream.
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

    writer({"node": "generate_html", "status": "done", "label": "HTML generation complete"})
    return {
        "html_code": html,
        "messages":  [AIMessage(content="Reveal.js HTML generated.")],
    }


def validate_html(state: PresentationState) -> dict:
    writer = get_stream_writer()
    writer({"node": "validate_html", "status": "running", "label": "Validating HTML..."})

    html = state.get("html_code", "")
    if "reveal.js" not in html:
        raise ValueError("Missing reveal.js CDN — generation failed")
    if "<section" not in html:
        raise ValueError("Missing slide sections")
    if len(html) < 500:
        raise ValueError("HTML too short — generation likely failed")

    writer({"node": "validate_html", "status": "done", "label": "Validation passed"})
    return {}


# ── Graph ──────────────────────────────────────────────────────────────────

# Checkpointer so the server can call get_state(config) after streaming
# to read the final html_code and save/preview the presentation.
_checkpointer = MemorySaver()

def create_graph():
    builder = StateGraph(PresentationState)

    builder.add_node("generate_content", generate_content)
    builder.add_node("generate_design",  generate_design)
    builder.add_node("assemble_outline", assemble_outline)
    builder.add_node("generate_html",    generate_html)
    builder.add_node("validate_html",    validate_html)

    builder.add_edge(START,              "generate_content")
    builder.add_edge(START,              "generate_design")
    builder.add_edge("generate_content", "assemble_outline")
    builder.add_edge("generate_design",  "assemble_outline")
    builder.add_edge("assemble_outline", "generate_html")
    builder.add_edge("generate_html",    "validate_html")
    builder.add_edge("validate_html",    END)

    return builder.compile(checkpointer=_checkpointer)
