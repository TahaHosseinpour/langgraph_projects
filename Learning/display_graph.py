"""Render every Learning graph as a Mermaid PNG into the images/ folder.

- Run as a plain script:  python display_graph.py
- Each graph is saved to  images/<module_name>.png
  (e.g. images/graph_01_basic.png, images/graph_02_conditional.png, ...).
- In a Jupyter / interactive window it also shows each diagram inline.

Rendering uses the mermaid.ink API (needs internet).
"""

import importlib
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables before importing the graphs — the LLM clients are
# constructed on import, so OPENAI_API_KEY must be available first.
_here = Path(__file__).parent
load_dotenv(_here / ".env")

IMAGES_DIR = _here / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# The six example graphs, in order. The file name doubles as the image name.
GRAPHS = [
    "graph_01_basic",
    "graph_02_conditional",
    "graph_03_hitl",
    "graph_04_time_travel",
    "graph_05_memory",
    "graph_06_streaming",
]


def main() -> None:
    saved = 0
    for name in GRAPHS:
        try:
            module = importlib.import_module(f"graphs.{name}")
            graph  = module.create_graph()
            png    = graph.get_graph().draw_mermaid_png()
        except Exception as exc:  # keep going even if one diagram fails
            print(f"FAILED  {name}: {exc}")
            continue

        out = IMAGES_DIR / f"{name}.png"
        out.write_bytes(png)
        saved += 1
        print(f"Saved   images/{out.name}")

        # Show inline when run inside Jupyter / an interactive window.
        try:
            from IPython.display import Image, display
            display(Image(png))
        except Exception:
            pass

    print(f"\nDone — {saved}/{len(GRAPHS)} diagrams in {IMAGES_DIR}")


if __name__ == "__main__":
    main()
