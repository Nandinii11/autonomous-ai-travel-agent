"""Terminal demo:  python cli.py [--chaos]     (type 'quit' to exit)"""
import sys

from agent import ICON, run_agent

chaos = "--chaos" in sys.argv
memory = {}
print(f"Travel Agent ready (failure simulation {'ON' if chaos else 'OFF'}). Ask me to plan a trip!\n")
while True:
    try:
        q = input("you> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if q.lower() in ("quit", "exit"):
        break
    print()
    r = run_agent(q, memory, chaos, lambda node, out: [print(f"  {ICON[e['kind']]} [{e['node']}] {e['text']}") for e in out.get("trace", [])])
    memory = r["memory"]
    print("\n" + r["answer"] + "\n")
