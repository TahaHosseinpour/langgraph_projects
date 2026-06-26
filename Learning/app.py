import uuid
import json
import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv()

# ── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LangGraph Slide Agent",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Hide default sidebar toggle */
[data-testid="collapsedControl"] { display: none; }
[data-testid="stSidebar"] { display: none; }

/* App background */
.stApp { background: #F0F4FF; }

/* Left panel card */
.chat-card {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #D0DEFF;
    height: calc(100vh - 80px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(30,111,235,0.08);
}

/* Right panel card */
.preview-card {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #D0DEFF;
    height: calc(100vh - 80px);
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(30,111,235,0.08);
}

/* Graph selector */
.stSelectbox > div > div {
    background: #F0F4FF !important;
    border: 1.5px solid #1E6FEB !important;
    border-radius: 10px !important;
    color: #1A1A2E !important;
    font-weight: 600;
}

/* Buttons */
.stButton > button {
    border-radius: 10px !important;
    border: 1.5px solid #1E6FEB !important;
    color: #1E6FEB !important;
    background: white !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: #1E6FEB !important;
    color: white !important;
}
.stButton > button[kind="primary"] {
    background: #1E6FEB !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1558c0 !important;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    margin-bottom: 8px;
}

/* Chat input */
[data-testid="stChatInput"] {
    border-radius: 12px !important;
}

/* Progress node badges */
.node-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    margin: 2px 0;
}
.node-running { background: #FFF3CD; color: #856404; border: 1px solid #FFDDA6; }
.node-done    { background: #D1FAE5; color: #065F46; border: 1px solid #6EE7B7; }
.node-error   { background: #FEE2E2; color: #991B1B; border: 1px solid #FCA5A5; }

/* Memory indicator */
.memory-tag {
    background: #EDE9FE;
    color: #5B21B6;
    border: 1px solid #C4B5FD;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}

/* Checkpoint button */
.cp-btn {
    background: #FFF7ED;
    border: 1px solid #FED7AA;
    border-radius: 8px;
    color: #C2410C;
    padding: 4px 12px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
}

div[data-testid="stVerticalBlock"] { gap: 0; }
</style>
""", unsafe_allow_html=True)


# ── Graph registry ───────────────────────────────────────────────────────────

GRAPH_META = {
    "1 — Basic":             {"module": "graphs.graph_01_basic",       "features": []},
    "2 — Conditional Edges": {"module": "graphs.graph_02_conditional",  "features": ["conditional"]},
    "3 — Human in the Loop": {"module": "graphs.graph_03_hitl",        "features": ["hitl"]},
    "4 — Time Travel":       {"module": "graphs.graph_04_time_travel",  "features": ["time_travel"]},
    "5 — Long-term Memory":  {"module": "graphs.graph_05_memory",       "features": ["memory"]},
    "6 — Streaming":         {"module": "graphs.graph_06_streaming",    "features": ["streaming"]},
}

@st.cache_resource
def load_graph(module_path: str):
    import importlib
    mod = importlib.import_module(module_path)
    return mod.create_graph()


# ── Session state init ───────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "thread_id":      str(uuid.uuid4()),
        "chat_history":   [],
        "jsx_code":       None,
        "slides":         None,
        "design_system":  None,
        "awaiting_hitl":  False,
        "hitl_data":      None,
        "hitl_config":    None,
        "tt_error":       None,
        "tt_config":      None,
        "tt_graph":       None,
        "memory_hint":    None,
        "selected_graph": list(GRAPH_META.keys())[0],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


def _reset_for_new_graph():
    for key in ["jsx_code", "slides", "design_system", "awaiting_hitl",
                "hitl_data", "hitl_config", "tt_error", "tt_config", "tt_graph", "memory_hint"]:
        st.session_state[key] = None if key not in ["awaiting_hitl"] else False
    st.session_state["chat_history"] = []
    st.session_state["thread_id"] = str(uuid.uuid4())


# ── React slide renderer ─────────────────────────────────────────────────────

def render_slide_preview(jsx_code: str, height: int = 520):
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ overflow: hidden; background: #0a0a1a; }}
    #root {{ width: 100%; height: 100vh; }}
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    {jsx_code}
    const domNode = document.getElementById('root');
    const root = ReactDOM.createRoot(domNode);
    root.render(<Presentation />);
  </script>
</body>
</html>"""
    st.components.v1.html(html, height=height, scrolling=False)


# ── Build initial input ──────────────────────────────────────────────────────

def _parse_user_prompt(prompt: str) -> dict:
    parts = [p.strip() for p in prompt.split(",")]
    topic    = parts[0] if len(parts) > 0 else prompt
    audience = parts[1] if len(parts) > 1 else "general audience"
    tone_raw = parts[2].lower() if len(parts) > 2 else "formal"
    tone     = tone_raw if tone_raw in ("formal", "casual", "technical") else "formal"
    try:
        num_slides = int(parts[3]) if len(parts) > 3 else 6
    except ValueError:
        num_slides = 6

    return {
        "request": {
            "topic":      topic,
            "audience":   audience,
            "num_slides": num_slides,
            "tone":       tone,
        },
        "design_system": {},
        "slides":        [],
        "jsx_code":      "",
        "approved":      False,
        "messages":      [],
    }


# ── Graph runners ────────────────────────────────────────────────────────────

def _run_basic(graph, initial_state: dict):
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Running graph... please wait."
    })

    with st.spinner("Running graph..."):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        result = graph.invoke(initial_state, config)

    st.session_state.jsx_code      = result["jsx_code"]
    st.session_state.slides        = result["slides"]
    st.session_state.design_system = result["design_system"]
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": f"Done! Generated {len(result['slides'])} slides."
    })


def _run_conditional(graph, initial_state: dict):
    tone = initial_state["request"]["tone"]
    path = "technical path" if tone == "technical" else "casual/creative path"
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": f"Routing via conditional edge → **{path}**"
    })

    with st.spinner("Running graph (conditional routing)..."):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        result = graph.invoke(initial_state, config)

    st.session_state.jsx_code      = result["jsx_code"]
    st.session_state.slides        = result["slides"]
    st.session_state.design_system = result["design_system"]
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": f"Done via **{path}**! {len(result['slides'])} slides generated."
    })


def _run_hitl_phase1(graph, initial_state: dict):
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Generating content and design... then pausing for your review."
    })

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    with st.spinner("Running until human review checkpoint..."):
        for chunk in graph.stream(initial_state, config, stream_mode="updates"):
            for node_name, data in chunk.items():
                if node_name == "__interrupt__":
                    interrupt_val = data[0].value
                    st.session_state.awaiting_hitl = True
                    st.session_state.hitl_data     = interrupt_val
                    st.session_state.hitl_config   = config
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "Paused at **Human Review**. Edit the design and slides in the panel on the right, then approve."
                    })
                    return


def _run_hitl_resume(graph, edited_data: dict):
    config = st.session_state.hitl_config
    with st.spinner("Resuming from human review..."):
        result = graph.invoke(Command(resume=edited_data), config)

    st.session_state.jsx_code      = result["jsx_code"]
    st.session_state.slides        = result["slides"]
    st.session_state.design_system = result["design_system"]
    st.session_state.awaiting_hitl = False
    st.session_state.hitl_data     = None
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Review accepted. JSX generated successfully!"
    })


def _run_time_travel(graph, initial_state: dict):
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Running with checkpointing enabled. If validation fails, you can travel back to **assemble_outline**."
    })

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    try:
        with st.spinner("Running graph (checkpointing active)..."):
            result = graph.invoke(initial_state, config)

        st.session_state.jsx_code      = result["jsx_code"]
        st.session_state.slides        = result["slides"]
        st.session_state.design_system = result["design_system"]
        st.session_state.tt_error      = None
        st.session_state.tt_config     = config
        st.session_state.tt_graph      = graph
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Done! {len(result['slides'])} slides. You can use **Simulate Error** to test time travel."
        })

    except Exception as e:
        st.session_state.tt_error  = str(e)
        st.session_state.tt_config = config
        st.session_state.tt_graph  = graph
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Validation error: `{e}` — Use **Time Travel** in the panel to go back."
        })


def _run_memory(graph, initial_state: dict):
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Running with long-term memory. Design preferences are read/saved across sessions."
    })

    with st.spinner("Running graph (memory active)..."):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        result = graph.invoke(initial_state, config)

    st.session_state.jsx_code      = result["jsx_code"]
    st.session_state.slides        = result["slides"]
    st.session_state.design_system = result["design_system"]

    from graphs import graph_05_memory as g5
    items = g5.store.search(g5._USER_NS)
    if items:
        pref = items[0].value
        st.session_state.memory_hint = pref

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": f"Done! Style preference saved for next time."
    })


def _run_streaming(graph, initial_state: dict, progress_placeholder, preview_placeholder):
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    partial_jsx = ""

    node_status: dict[str, str] = {}

    def _render_progress():
        lines = []
        for node, status in node_status.items():
            cls = "node-running" if status == "running" else "node-done"
            icon = "⟳" if status == "running" else "✓"
            lines.append(f'<span class="node-badge {cls}">{icon} {node}</span>')
        progress_placeholder.markdown(" &nbsp; ".join(lines), unsafe_allow_html=True)

    for chunk in graph.stream(initial_state, config, stream_mode=["messages", "custom"]):
        mode, data = chunk

        if mode == "custom":
            evt = data
            node  = evt.get("node", "")
            status = evt.get("status", "")
            label  = evt.get("label", "")
            node_status[node] = status
            _render_progress()
            if status == "running":
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"**{node}** — {label}"
                })

        elif mode == "messages":
            token, metadata = data
            langgraph_node = metadata.get("langgraph_node", "")
            if langgraph_node == "generate_jsx" and hasattr(token, "content") and token.content:
                partial_jsx += token.content
                preview_placeholder.empty()
                with preview_placeholder.container():
                    if "export default" in partial_jsx:
                        try:
                            render_slide_preview(partial_jsx, height=480)
                        except Exception:
                            st.code(partial_jsx[:500] + "...", language="jsx")
                    else:
                        st.code(partial_jsx[-300:] if len(partial_jsx) > 300 else partial_jsx, language="jsx")

    # Finalize from graph state
    final = graph.get_state(config)
    if final and final.values:
        st.session_state.jsx_code      = final.values.get("jsx_code", partial_jsx)
        st.session_state.slides        = final.values.get("slides")
        st.session_state.design_system = final.values.get("design_system")

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Streaming complete! Presentation ready."
    })


# ── HITL dialog ──────────────────────────────────────────────────────────────

@st.dialog("Review & Edit Presentation", width="large")
def hitl_dialog(hitl_data: dict):
    design = hitl_data["design_system"]
    slides = hitl_data["slides"]

    tab_design, tab_slides = st.tabs(["Design System", "Slides"])

    with tab_design:
        st.markdown("#### Colors")
        c = design["colors"]
        col1, col2 = st.columns(2)
        with col1:
            new_primary    = st.color_picker("Primary Background",   c["primary_bg"],    key="hp_primary")
            new_secondary  = st.color_picker("Secondary Background", c["secondary_bg"],  key="hp_secondary")
            new_accent     = st.color_picker("Accent",               c["accent"],        key="hp_accent")
        with col2:
            new_text_p     = st.color_picker("Text Primary",   c["text_primary"],   key="hp_text_p")
            new_text_s     = st.color_picker("Text Secondary", c["text_secondary"], key="hp_text_s")

        st.markdown("#### Typography")
        t = design["typography"]
        col3, col4 = st.columns(2)
        with col3:
            new_font    = st.selectbox("Font Family", ["Inter", "Space Grotesk", "Roboto Mono", "Playfair Display"],
                                       index=["Inter", "Space Grotesk", "Roboto Mono", "Playfair Display"].index(t["font_family"])
                                       if t["font_family"] in ["Inter", "Space Grotesk", "Roboto Mono", "Playfair Display"] else 0,
                                       key="hp_font")
            new_layout  = st.selectbox("Layout Style", ["minimal", "bold", "editorial"],
                                       index=["minimal", "bold", "editorial"].index(design["layout_style"])
                                       if design["layout_style"] in ["minimal", "bold", "editorial"] else 0,
                                       key="hp_layout")
        with col4:
            new_heading_sz = st.number_input("Heading Size (px)", min_value=48, max_value=120, value=t["heading_size"], key="hp_h_sz")
            new_body_sz    = st.number_input("Body Size (px)",    min_value=24, max_value=72,  value=t["body_size"],    key="hp_b_sz")

    with tab_slides:
        edited_slides = []
        for slide in slides:
            with st.expander(f"Slide {slide['index'] + 1}: {slide['title']}", expanded=False):
                new_title   = st.text_input("Title",       slide["title"],   key=f"hs_title_{slide['index']}")
                new_layout_hint = st.selectbox(
                    "Layout",
                    ["hero", "bullets", "two-column", "quote"],
                    index=["hero", "bullets", "two-column", "quote"].index(slide["layout_hint"])
                    if slide["layout_hint"] in ["hero", "bullets", "two-column", "quote"] else 1,
                    key=f"hs_layout_{slide['index']}"
                )
                content_str = st.text_area(
                    "Content (one item per line)",
                    "\n".join(slide["content"]),
                    height=120,
                    key=f"hs_content_{slide['index']}"
                )
                edited_slides.append({
                    **slide,
                    "title":       new_title,
                    "layout_hint": new_layout_hint,
                    "content":     [l.strip() for l in content_str.split("\n") if l.strip()],
                })

    st.divider()
    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("Approve", type="primary", key="hitl_approve"):
            edited_design = {
                "colors": {
                    "primary_bg":    new_primary,
                    "secondary_bg":  new_secondary,
                    "accent":        new_accent,
                    "text_primary":  new_text_p,
                    "text_secondary": new_text_s,
                },
                "typography": {
                    "font_family":    new_font,
                    "heading_size":   new_heading_sz,
                    "body_size":      new_body_sz,
                    "weight_heading": t["weight_heading"],
                    "weight_body":    t["weight_body"],
                },
                "layout_style": new_layout,
            }
            st.session_state.hitl_approved_data = {
                "design_system": edited_design,
                "slides":        edited_slides,
            }
            st.rerun()
    with col_b:
        if st.button("Cancel", key="hitl_cancel"):
            st.rerun()


# ── Layout ───────────────────────────────────────────────────────────────────

col_left, col_right = st.columns([5, 7], gap="medium")

# ── LEFT PANEL ───────────────────────────────────────────────────────────────

with col_left:
    st.markdown('<div class="chat-card">', unsafe_allow_html=True)

    # Graph selector
    prev_graph = st.session_state.selected_graph
    selected   = st.selectbox(
        "Select Graph",
        list(GRAPH_META.keys()),
        key="selected_graph",
        label_visibility="collapsed",
    )
    if selected != prev_graph:
        _reset_for_new_graph()
        st.rerun()

    features = GRAPH_META[selected]["features"]

    # Feature badge
    badge_map = {
        "conditional":  ("Conditional Edges", "#EFF6FF", "#1E6FEB"),
        "hitl":         ("Human in the Loop", "#FFF7ED", "#C2410C"),
        "time_travel":  ("Time Travel",       "#F0FDF4", "#15803D"),
        "memory":       ("Long-term Memory",  "#EDE9FE", "#6D28D9"),
        "streaming":    ("Streaming",         "#FFF1F2", "#BE123C"),
    }
    for feat in features:
        label, bg, color = badge_map[feat]
        st.markdown(
            f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
            f'border-radius:8px;padding:3px 10px;font-size:12px;font-weight:600;">{label}</span>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Chat messages
    chat_box = st.container(height=480, border=False)
    with chat_box:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Memory indicator (graph 5)
    if "memory" in features and st.session_state.memory_hint:
        pref = st.session_state.memory_hint
        st.markdown(
            f'<div class="memory-tag">Memory: {pref.get("font_family","?")} · '
            f'{pref.get("layout_style","?")} · accent {pref.get("accent","?")}</div>',
            unsafe_allow_html=True
        )

    # Chat input
    prompt = st.chat_input(
        "topic, audience, tone, num_slides  (e.g. LangGraph, developers, technical, 7)"
    )
    st.markdown('</div>', unsafe_allow_html=True)


# ── RIGHT PANEL ──────────────────────────────────────────────────────────────

with col_right:
    st.markdown('<div class="preview-card">', unsafe_allow_html=True)

    # Time travel controls (graph 4)
    if "time_travel" in features:
        tt_col1, tt_col2 = st.columns([3, 1])
        with tt_col2:
            if st.button("Simulate Error", key="tt_simulate"):
                st.session_state.jsx_code = "broken jsx without export"
                st.session_state.tt_error = "JSX missing 'export default' — simulated for demo"
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "Error simulated! Click **Time Travel** to go back to `assemble_outline`."
                })
                st.rerun()

        if st.session_state.tt_error and st.session_state.tt_config:
            with tt_col1:
                st.error(f"Error: {st.session_state.tt_error}")
            if st.button("↩ Time Travel → assemble_outline", key="tt_go_back"):
                graph_tt   = st.session_state.tt_graph
                config_tt  = st.session_state.tt_config
                history    = list(graph_tt.get_state_history(config_tt))
                target = next(
                    (cp for cp in history if "assemble_outline" in str(cp.metadata.get("writes", {}))),
                    None
                )
                if target:
                    with st.spinner("Travelling back to assemble_outline and regenerating..."):
                        result = graph_tt.invoke(None, target.config)
                    st.session_state.jsx_code      = result["jsx_code"]
                    st.session_state.slides        = result["slides"]
                    st.session_state.design_system = result["design_system"]
                    st.session_state.tt_error      = None
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "Time travel successful! Replayed from `assemble_outline`."
                    })
                    st.rerun()
                else:
                    st.warning("No assemble_outline checkpoint found. Run the graph first.")

    # Streaming progress area (graph 6)
    progress_area  = st.empty()
    preview_area   = st.empty()

    # HITL panel (graph 3)
    if "hitl" in features and st.session_state.awaiting_hitl and st.session_state.hitl_data:
        if "hitl_approved_data" in st.session_state and st.session_state.hitl_approved_data:
            approved = st.session_state.pop("hitl_approved_data")
            graph_hitl = load_graph(GRAPH_META[selected]["module"])
            _run_hitl_resume(graph_hitl, approved)
            st.rerun()
        else:
            hitl_dialog(st.session_state.hitl_data)

    # Slide preview
    if st.session_state.jsx_code and not st.session_state.awaiting_hitl and not st.session_state.tt_error:
        preview_area.empty()
        with preview_area.container():
            render_slide_preview(st.session_state.jsx_code, height=520)
    elif not st.session_state.awaiting_hitl and not st.session_state.tt_error:
        with preview_area.container():
            st.markdown(
                "<div style='display:flex;align-items:center;justify-content:center;"
                "height:400px;color:#94a3b8;font-size:18px;'>"
                "Enter a topic in the chat to generate a presentation"
                "</div>",
                unsafe_allow_html=True
            )

    st.markdown('</div>', unsafe_allow_html=True)


# ── Handle user input ────────────────────────────────────────────────────────

if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    initial_state = _parse_user_prompt(prompt)
    graph = load_graph(GRAPH_META[selected]["module"])

    if selected == "1 — Basic":
        _run_basic(graph, initial_state)

    elif selected == "2 — Conditional Edges":
        _run_conditional(graph, initial_state)

    elif selected == "3 — Human in the Loop":
        _run_hitl_phase1(graph, initial_state)

    elif selected == "4 — Time Travel":
        _run_time_travel(graph, initial_state)

    elif selected == "5 — Long-term Memory":
        _run_memory(graph, initial_state)

    elif selected == "6 — Streaming":
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "Streaming started — watch the preview update live!"
        })
        _run_streaming(graph, initial_state, progress_area, preview_area)

    st.rerun()
