"""Streamlit app for users to ask and get responses to their D&D questions."""

import streamlit as st

EDITIONS: dict[str, str | None] = {
    "2014 (SRD 5.1)": "srd51",
    "2024 (SRD 5.2)": "srd52",
    "Both": None,
}

st.title("RAG D&D Lawyer")
st.caption("Answers grounded in the D&D 5e SRD (CC-BY-4.0, Wizards of the Coast)")

question = st.text_input("Enter your question")
selected_edition = st.radio("Select Edition", list(EDITIONS), horizontal=True, index=2)

st.write(question)
st.write(f"Selected Edition: {selected_edition}")
