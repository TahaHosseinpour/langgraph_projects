"""Node functions for the data analysis agent."""

import os

import pandas as pd
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from my_agent.utils.state import DataAnalysisState
from my_agent.utils.tools import run_python

# base_url is read from OPENAI_BASE_URL so a custom/compatible endpoint can be used.
model = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    base_url=os.getenv("OPENAI_BASE_URL"),
)


def _data_preview(data_path: str) -> str:
    """Return a small textual preview of the dataset for prompting."""
    try:
        df = pd.read_csv(data_path)
    except Exception as exc:  # noqa: BLE001
        return f"Could not read data: {exc}"
    return (
        f"Columns: {list(df.columns)}\n"
        f"Shape: {df.shape}\n"
        f"Head:\n{df.head().to_string()}"
    )


def _strip_code_fences(text: str) -> str:
    """Remove markdown ``` fences so the code can be executed directly."""
    code = text.strip()
    if code.startswith("```"):
        # Drop the opening fence (and optional language hint) and closing fence.
        code = code.split("```", 2)[1]
        if code.lower().startswith("python"):
            code = code[len("python"):]
    return code.strip()


def generate_hypothesis(state: DataAnalysisState) -> dict:
    """Inspect the data and generate a hypothesis to investigate."""
    preview = _data_preview(state["data_path"])
    system = SystemMessage(
        content=(
            "You are a data scientist. Given a dataset preview and a user "
            "question, state one clear, testable hypothesis you can check with "
            "pandas. Keep it to 1-2 sentences."
        )
    )
    response = model.invoke(
        [system, HumanMessage(content=f"Question: {state['question']}\n\n{preview}")]
    )
    hypothesis = response.text()
    return {
        "hypothesis": hypothesis,
        "iteration_count": 0,
        "messages": [AIMessage(content=f"Hypothesis: {hypothesis}")],
    }


def analyze_data(state: DataAnalysisState) -> dict:
    """Write and execute pandas code to test the hypothesis."""
    preview = _data_preview(state["data_path"])

    # Include the previous error (if any) so the model can self-correct.
    last_result = state["analysis_result"][-1] if state["analysis_result"] else ""
    retry_hint = ""
    if last_result.startswith(("Error", "Failed")):
        retry_hint = f"\n\nThe previous attempt failed:\n{last_result}\nFix it."

    system = SystemMessage(
        content=(
            "You are a data analyst. Write python code using the pandas "
            "DataFrame `df` to test the hypothesis. Use print() to show "
            "results. Return only the code, with no markdown fences."
        )
    )
    response = model.invoke(
        [
            system,
            HumanMessage(
                content=f"Hypothesis: {state['hypothesis']}\n\n{preview}{retry_hint}"
            ),
        ]
    )
    code = _strip_code_fences(response.text())
    result = run_python.invoke({"code": code, "data_path": state["data_path"]})
    return {
        "analysis_code": code,
        "analysis_result": [result],
        "iteration_count": state["iteration_count"] + 1,
        "messages": [AIMessage(content=f"Analysis result:\n{result}")],
    }


def write_report(state: DataAnalysisState) -> dict:
    """Summarize the analysis into a final markdown report."""
    results = "\n\n".join(state["analysis_result"])
    system = SystemMessage(
        content=(
            "You are a data analyst writing a final report. Using the question, "
            "hypothesis and analysis results, write a concise markdown report: "
            "restate the question, the hypothesis, what the analysis found, and "
            "a short conclusion."
        )
    )
    response = model.invoke(
        [
            system,
            HumanMessage(
                content=(
                    f"Question: {state['question']}\n"
                    f"Hypothesis: {state['hypothesis']}\n\n"
                    f"Analysis results:\n{results}"
                )
            ),
        ]
    )
    return {"report": response.text()}


def should_reanalyze(state: DataAnalysisState) -> str:
    """Decide whether to retry the analysis or write the report."""
    last_result = state["analysis_result"][-1] if state["analysis_result"] else ""
    failed = last_result.startswith(("Error", "Failed"))
    if failed and state["iteration_count"] < state["max_iterations"]:
        return "retry"
    return "report"
