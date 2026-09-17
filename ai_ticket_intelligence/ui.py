from __future__ import annotations

import os
import requests
import pandas as pd
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="AI Ticket Intelligence", page_icon="🎫", layout="wide")
st.title("🎫 AI Customer Support Ticket Intelligence")
st.caption("LLM-assisted natural-language analytics with deterministic, allow-listed execution")

def get_json(path: str):
    r=requests.get(f"{API_URL}{path}",timeout=10); r.raise_for_status(); return r.json()

try:
    health=get_json("/health")
    st.success(f"Backend ready • {health['rows']} tickets • reference {health['reference_time']} • planner {health['llm_provider']}")
except Exception as e:
    st.error(f"Backend unavailable at {API_URL}: {e}")
    health=None

st.subheader("Ask the dataset")
examples=[
    "How many tickets are currently open?",
    "How many critical tickets are unresolved?",
    "Which agent resolved the most tickets?",
    "Which agent has the lowest average customer rating?",
    "What is the average customer rating for Technical category tickets?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "Are there any anomalies in resolution times this week?",
]
question=st.text_input("Natural-language question", placeholder=examples[0])
with st.expander("Example questions"):
    for x in examples: st.code(x, language=None)
if st.button("Run Query", type="primary", disabled=not question.strip()):
    try:
        r=requests.post(f"{API_URL}/query",json={"question":question},timeout=60); r.raise_for_status(); data=r.json()
        st.markdown("### Answer")
        st.info(data["answer"])
        if data.get("rows"):
            st.dataframe(pd.DataFrame(data["rows"]), use_container_width=True, hide_index=True)
        with st.expander("Interpreted safe query plan"):
            st.json(data["plan"])
        with st.expander("Metadata"):
            st.json(data["metadata"])
    except Exception as e: st.error(str(e))

st.divider()
st.subheader("Anomaly Detection")
window=st.selectbox("Window", ["All data","Latest week","Latest month"])
param={"All data":"","Latest week":"?relative_window=latest_week","Latest month":"?relative_window=latest_month"}[window]
if st.button("Run Anomaly Detection"):
    try:
        data=get_json(f"/anomalies{param}")
        c1,c2,c3=st.columns(3)
        c1.metric("Long resolution",data["counts"]["abnormally_long_resolution"]); c2.metric("Stale high priority",data["counts"]["unresolved_high_priority_older_than_24h"]); c3.metric("Total flags",data["counts"]["total_flags"])
        st.caption(f"Reference time: {data['reference_time']}")
        st.markdown("#### Abnormally long resolution times")
        st.dataframe(pd.DataFrame(data["details"]["abnormally_long_resolution"]),use_container_width=True,hide_index=True)
        st.markdown("#### Unresolved High/Critical tickets older than 24h")
        st.dataframe(pd.DataFrame(data["details"]["unresolved_high_priority_older_than_24h"]),use_container_width=True,hide_index=True)
        with st.expander("Rules and thresholds"): st.json(data["rules"])
    except Exception as e: st.error(str(e))
