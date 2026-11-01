"""Streamlit demo UI:  python -m streamlit run app.py"""
import os

import streamlit as st

import llm
from agent import GRAPH, ICON, run_agent

st.set_page_config(page_title="Autonomous Travel Agent", page_icon="✈️", layout="wide")
st.title(" Autonomous Travel Agent")
st.caption("LangGraph multi-step agent · dynamic tool calling · self-correction · short-term memory")

ss = st.session_state
ss.setdefault("messages", [])   # [{role, content, trace}]
ss.setdefault("memory", {})     # short-term context carried between turns

with st.sidebar:
    st.header("Demo controls")
    chaos = st.toggle("💥 Simulate tool failures", value=False,
                      help="Flight API outage, weather timeout, empty hotel search - watch the agent retry, fall back and adapt.")
    # key = st.text_input("Groq API key", type="password", value=os.getenv("GROQ_API_KEY", ""),
    #                     help="Optional. Stored only in this session's environment.")
    # if key:
    #     os.environ["GROQ_API_KEY"] = key
    # else:
    #     os.environ.pop("GROQ_API_KEY", None)
    # st.write("Reasoning mode:", f"Groq LLM ({llm.MODEL}) + tools" if llm.available() else "rule-based + tools (no API key)")
    if st.button("🗑 Reset conversation"):
        ss.messages, ss.memory = [], {}
        st.rerun()
    st.subheader("Try these")
    examples = ["Plan a 4 day trip to Goa from Mumbai for 2 people under 60000, beach and food",
                "make it cheaper", "extend by 2 days", "weather in Jaipur",
                "5 day Dubai trip, luxury, 3 lakh, show in USD", "plan 3 days in Manali for 4 people budget 8000",
                "plan a trip to Tokyo"]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            ss.pending = ex
    with st.expander("Agent graph (Mermaid)"):
        st.code(GRAPH.get_graph().draw_mermaid(), language="text")
    with st.expander("Memory (short-term context)"):
        st.json(ss.memory or {})


def render_trace(trace, container):
    for e in trace:
        container.markdown(f"{ICON[e['kind']]} **{e['node']}** · {e['text']}")


for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("trace"):
            with st.expander("🔍 Agent trace (thoughts, tool calls, observations)"):
                render_trace(m["trace"], st)

prompt = st.chat_input("e.g. Plan a 3 day trip to Jaipur from Delhi for 2 people under 25000") or ss.pop("pending", None)
if prompt:
    ss.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        status = st.status("🧠 Agent working...", expanded=True)

        def on_event(node, out):
            render_trace(out.get("trace", []), status)

        result = run_agent(prompt, ss.memory, chaos, on_event)
        status.update(label="Agent finished - open to inspect the trace", state="complete", expanded=False)
        st.markdown(result["answer"])
    ss.memory = result["memory"]
    ss.messages.append({"role": "assistant", "content": result["answer"], "trace": result["trace"]})
    st.rerun()
