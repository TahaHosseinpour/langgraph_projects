"""Display the compiled graph as a Mermaid image.

- In a plain terminal: saves the diagram to graph.png.
- In a Jupyter notebook / interactive window: also shows it inline.
"""

from dotenv import load_dotenv
from IPython.display import Image, display

# Load environment variables before importing the graph (the model is built on import).
load_dotenv()

from my_agent.agent import graph  # noqa: E402 - must import after load_dotenv()

# Render the graph as a Mermaid PNG (uses the mermaid.ink API, needs internet).
png = graph.get_graph().draw_mermaid_png()

# Save to a file so it can be viewed when run as a plain script.
with open("graph.png", "wb") as file:
    file.write(png)
print("Saved graph.png")

# Also show it inline when run inside Jupyter / an interactive window.
display(Image(png))
