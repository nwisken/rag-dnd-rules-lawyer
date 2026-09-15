"""Streamlit app for users to ask and get responses to their D&D questions."""

from typing import Any

import httpx
import streamlit as st

API_URL = "http://localhost:8000/ask"
FEEDBACK_URL = "http://localhost:8000/feedback"

EDITIONS: dict[str, str | None] = {
    "2014 (SRD 5.1)": "srd51",
    "2024 (SRD 5.2)": "srd52",
    "Both": None,
}
EDITION_LABELS = {code: label for label, code in EDITIONS.items()}


def render_answer(data: dict[str, Any]) -> None:
    """Renders one /ask response: the answer, then its retrieved sources.

    Args:
        data: a decoded AskResponse — {"answer": str, "sources": list[dict]}.
    """
    st.markdown(data["answer"])
    for source in data["sources"]:
        edition = EDITION_LABELS[source["edition"]]
        score = source["score"]
        st.markdown(f"- **{source['heading_path']}** — *{edition}* (score {score:.3f})")


def send_feedback(question: str, edition: str | None, data: dict[str, Any], verdict: str) -> None:
    """POSTs one thumbs verdict, with the sources that were on screen, to /feedback.

    Args:
        question: the question the user asked.
        edition: the edition filter used ("srd51"/"srd52"/None for Both).
        data: the rendered AskResponse the user is voting on.
        verdict: "up" or "down".
    """
    payload = {
        "question": question,
        "answer": data["answer"],
        "edition": edition,
        "verdict": verdict,
        "retrieved_paths": [s["heading_path"] for s in data["sources"]],
    }
    try:
        httpx.post(FEEDBACK_URL, json=payload, timeout=10).raise_for_status()
    except httpx.HTTPError:
        st.warning("Couldn't record that feedback.")
    else:
        st.session_state.feedback_sent = verdict


st.title("RAG D&D Lawyer")
st.caption("Answers grounded in the D&D 5e SRD (CC-BY-4.0, Wizards of the Coast)")

question = st.text_input("Enter your question")
selected_edition = st.radio("Select Edition", list(EDITIONS), horizontal=True, index=2)
edition_code = EDITIONS[selected_edition]

# The cache key: a new answer is fetched only when the question or edition changes,
# so clicking a thumb re-runs the script without re-hitting /ask.
current_key = (question, edition_code)
cached = st.session_state.get("result")

if question and (cached is None or cached["key"] != current_key):
    payload = {"question": question, "edition": edition_code}
    try:
        response = httpx.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except httpx.RequestError:
        st.error("Could not reach the API")
    except httpx.HTTPStatusError as err:
        st.error(f"The API returned an error ({err.response.status_code}).")
    else:
        st.session_state.result = {"key": current_key, "data": data}
        st.session_state.pop("feedback_sent", None)  # new answer, reset the vote
    cached = st.session_state.get("result")

# Render from the cache so a thumb click (which re-runs everything) redraws the same answer.
if cached and cached["key"] == current_key:
    render_answer(cached["data"])

    col_up, col_down, _ = st.columns([1, 1, 8])
    if col_up.button("👍"):
        send_feedback(question, edition_code, cached["data"], "up")
    if col_down.button("👎"):
        send_feedback(question, edition_code, cached["data"], "down")

    if st.session_state.get("feedback_sent"):
        st.caption("Thanks — your feedback was recorded.")
