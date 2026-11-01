"""Optional LLM layer powered by Groq. If GROQ_API_KEY is set the agent uses the LLM for
understanding, tool selection and writing; otherwise it transparently falls back to rule-based logic."""
import json
import os
import re

MODEL = os.getenv("TRAVEL_AGENT_MODEL", "llama-3.3-70b-versatile")


def available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def ask(system: str, user: str, max_tokens: int = 700, json_mode: bool = False) -> str:
    from groq import Groq
    client = Groq()  # reads GROQ_API_KEY from the environment
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=max_tokens, temperature=0.2,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs)
    return resp.choices[0].message.content or ""


def ask_json(system: str, user: str) -> dict:
    text = ask(system + "\nReply with ONLY a JSON object.", user, json_mode=True)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)
