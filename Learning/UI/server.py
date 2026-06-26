import asyncio
import json
import queue
import re
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

_here = Path(__file__).parent
sys.path.insert(0, str(_here.parent))

_PRESENTATIONS_DIR = _here.parent / "presentations"
_PRESENTATIONS_DIR.mkdir(exist_ok=True)


def _save_presentation(html: str, topic: str, graph_id: str) -> str:
    slug     = re.sub(r"[^\w\-]", "_", topic.strip().lower())[:40]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"g{graph_id}_{slug}_{ts}.html"
    (_PRESENTATIONS_DIR / filename).write_text(html, encoding="utf-8")
    return filename


from dotenv import load_dotenv
load_dotenv(_here.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.types import Command

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_graphs: dict = {}


def _get_graph(gid: str):
    if gid not in _graphs:
        import importlib
        mods = {
            "1": "graphs.graph_01_basic",
            "2": "graphs.graph_02_conditional",
            "3": "graphs.graph_03_hitl",
            "4": "graphs.graph_04_time_travel",
            "5": "graphs.graph_05_memory",
            "6": "graphs.graph_06_streaming",
        }
        mod = importlib.import_module(mods[gid])
        _graphs[gid] = mod.create_graph()
    return _graphs[gid]


# ── Request models ──────────────────────────────────────────────────────────

class GenReq(BaseModel):
    graph_id:         str
    topic:            str
    audience:         str
    tone:             str
    num_slides:       int
    user_preferences: str = ""


class ResumeReq(BaseModel):
    thread_id:     str
    design_system: dict
    slides:        list


class ReplayReq(BaseModel):
    thread_id: str


def _state(r: GenReq) -> dict:
    return {
        "request":       {
            "topic":            r.topic,
            "audience":         r.audience,
            "num_slides":       r.num_slides,
            "tone":             r.tone,
            "user_preferences": r.user_preferences,
        },
        "design_system": {},
        "slides":        [],
        "html_code":     "",
        "approved":      False,
        "messages":      [],
    }


# ── Graphs 1, 2, 5 — invoke ────────────────────────────────────────────────

@app.post("/api/generate")
async def generate(req: GenReq):
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    try:
        result = await asyncio.to_thread(_get_graph(req.graph_id).invoke, _state(req), config)
    except Exception as e:
        raise HTTPException(500, str(e))

    mem = None
    if req.graph_id == "5":
        import graphs.graph_05_memory as g5
        items = g5.store.search(g5._USER_NS)
        if items:
            mem = items[0].value

    html     = result.get("html_code", "")
    filename = _save_presentation(html, req.topic, req.graph_id) if html else None

    return {
        "html_code":    html,
        "slides":       result.get("slides", []),
        "design_system": result.get("design_system", {}),
        "memory_hint":  mem,
        "saved_as":     filename,
    }


# ── Graph 3 — HITL ─────────────────────────────────────────────────────────

@app.post("/api/hitl/start")
async def hitl_start(req: GenReq):
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}
    g         = _get_graph("3")
    iv        = None

    def run():
        nonlocal iv
        for chunk in g.stream(_state(req), config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                iv = chunk["__interrupt__"][0].value
                return

    await asyncio.to_thread(run)
    if not iv:
        raise HTTPException(500, "No interrupt received")

    return {"thread_id": thread_id, "design_system": iv["design_system"], "slides": iv["slides"]}


@app.post("/api/hitl/resume")
async def hitl_resume(req: ResumeReq):
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        result = await asyncio.to_thread(
            _get_graph("3").invoke,
            Command(resume={"design_system": req.design_system, "slides": req.slides}),
            config,
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    html     = result.get("html_code", "")
    filename = _save_presentation(html, req.thread_id, "3") if html else None

    return {
        "html_code":     html,
        "slides":        result.get("slides", []),
        "design_system": result.get("design_system", {}),
        "saved_as":      filename,
    }


# ── Graph 4 — Time Travel ───────────────────────────────────────────────────

@app.post("/api/time-travel/run")
async def tt_run(req: GenReq):
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}
    g         = _get_graph("4")
    try:
        result   = await asyncio.to_thread(g.invoke, _state(req), config)
        html     = result.get("html_code", "")
        filename = _save_presentation(html, req.topic, "4") if html else None
        return {
            "thread_id":     thread_id,
            "error":         None,
            "html_code":     html,
            "slides":        result.get("slides", []),
            "design_system": result.get("design_system", {}),
            "saved_as":      filename,
        }
    except Exception as e:
        return {
            "thread_id":     thread_id,
            "error":         str(e),
            "html_code":     None,
            "slides":        [],
            "design_system": {},
        }


@app.post("/api/time-travel/replay")
async def tt_replay(req: ReplayReq):
    config  = {"configurable": {"thread_id": req.thread_id}}
    g       = _get_graph("4")
    history = list(g.get_state_history(config))
    target  = next(
        (cp for cp in history if "assemble_outline" in str(cp.metadata.get("writes", {}))),
        None,
    )
    if not target:
        raise HTTPException(404, "assemble_outline checkpoint not found — run the graph first")

    try:
        result   = await asyncio.to_thread(g.invoke, None, target.config)
        html     = result.get("html_code", "")
        filename = _save_presentation(html, f"replay_{req.thread_id[:8]}", "4") if html else None
        return {
            "html_code":     html,
            "slides":        result.get("slides", []),
            "design_system": result.get("design_system", {}),
            "saved_as":      filename,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Graph 6 — Streaming SSE ─────────────────────────────────────────────────

@app.post("/api/generate/stream")
async def stream_generate(req: GenReq):
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}
    g         = _get_graph("6")
    q: queue.Queue = queue.Queue()

    def run():
        try:
            for chunk in g.stream(_state(req), config, stream_mode=["updates", "custom"]):
                q.put(chunk)
        except Exception as e:
            q.put(("__error__", str(e)))
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    async def events():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, lambda: q.get(timeout=120))
            if item is None:
                break

            if isinstance(item, tuple) and len(item) == 2:
                mode, data = item

                if mode == "__error__":
                    yield f"data: {json.dumps({'type': 'error', 'message': data})}\n\n"
                    break
                elif mode == "custom":
                    yield f"data: {json.dumps({'type': 'progress', **data})}\n\n"
                elif mode == "updates":
                    for node_name, updates in data.items():
                        if node_name.startswith("__"):
                            continue
                        # A node that returns {} (e.g. validate_html) shows up as None here.
                        updates = updates or {}
                        payload = {"type": "node_done", "node": node_name}
                        if "slides" in updates:
                            payload["slides"] = updates["slides"]
                        if "design_system" in updates:
                            payload["design_system"] = updates["design_system"]
                        if "html_code" in updates:
                            payload["html_code"] = updates["html_code"]
                        yield f"data: {json.dumps(payload)}\n\n"

        try:
            final = g.get_state(config)
            if final and final.values:
                html     = final.values.get("html_code", "")
                filename = _save_presentation(html, req.topic, "6") if html else None
                payload  = {
                    "type":          "done",
                    "html_code":     html,
                    "slides":        final.values.get("slides", []),
                    "design_system": final.values.get("design_system", {}),
                    "saved_as":      filename,
                }
                yield f"data: {json.dumps(payload)}\n\n"
        except Exception:
            pass

        yield 'data: {"type":"end"}\n\n'

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Presentations list ──────────────────────────────────────────────────────

@app.get("/api/presentations")
async def list_presentations():
    files = sorted(
        _PRESENTATIONS_DIR.glob("*.html"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [f.name for f in files]


# ── Static files (more-specific mounts first) ───────────────────────────────

app.mount("/presentations", StaticFiles(directory=str(_PRESENTATIONS_DIR)), name="presentations")
app.mount("/", StaticFiles(directory=str(_here), html=True), name="static")
