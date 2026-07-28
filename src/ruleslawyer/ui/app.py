"""Streamlit app for users to ask and get responses to their D&D questions."""

from typing import Any

import httpx
import streamlit as st

API_URL = "http://localhost:8000/ask"

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
        distance = source["cosine_distance"]
        st.markdown(f"- **{source['heading_path']}** — *{edition}* (distance {distance:.3f})")


st.title("RAG D&D Lawyer")
st.caption("Answers grounded in the D&D 5e SRD (CC-BY-4.0, Wizards of the Coast)")

question = st.text_input("Enter your question")
selected_edition = st.radio("Select Edition", list(EDITIONS), horizontal=True, index=2)


# if question, fire question to API
if question:
    payload = {"question": question, "edition": EDITIONS[selected_edition]}

    try:
        response = httpx.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except httpx.RequestError:
        st.error("Could not reach the API")
    except httpx.HTTPStatusError as err:
        st.error(f"The API returned an error ({err.response.status_code}).")
    else:
        render_answer(data)
