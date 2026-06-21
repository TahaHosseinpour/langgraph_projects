"""Tools for the data analysis agent."""

import contextlib
import io

import pandas as pd
from langchain_core.tools import tool


@tool
def run_python(code: str, data_path: str) -> str:
    """Execute python code against a pandas DataFrame loaded from data_path.

    The code can use `df` (the loaded CSV) and `pd` (pandas). It should
    `print(...)` anything it wants to capture. Returns captured stdout.
    """
    try:
        df = pd.read_csv(data_path)
    except Exception as exc:  # noqa: BLE001 - report load failures as text
        return f"Failed to load data: {exc}"

    buffer = io.StringIO()
    # Local namespace exposed to the executed analysis code.
    local_env = {"df": df, "pd": pd}
    try:
        # exec is acceptable here: this is a local, developer-driven analysis
        # helper, not an endpoint exposed to untrusted input.
        with contextlib.redirect_stdout(buffer):
            exec(code, local_env)  # noqa: S102
    except Exception as exc:  # noqa: BLE001 - report runtime errors as text
        return f"Error while running code: {exc}"

    output = buffer.getvalue()
    return output or "Code ran but produced no output."
