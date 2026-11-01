"""Autonomous travel-planning agent built as a LangGraph state machine.

    understand --> plan --> execute --> reflect --+--> execute   (next step / retry / fallback / re-plan)
         |                                         |
         +--> END (needs clarification)            +--> compose --> END

* understand : turns free text (+ short-term memory of earlier turns) into a validated request
* plan       : task decomposition - chooses which tools are needed for THIS query
* execute    : calls exactly one tool
* reflect    : checks the observation; retries, switches to a fallback tool, relaxes constraints
               or re-plans (e.g. over budget -> cheaper hotel tier) before moving on
* compose    : builds the day-by-day itinerary and final answer
"""
import difflib
import math
import operator
import re
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

import llm
import tools as T
from data import DEST_ALIASES, DESTS, ORIGIN_ALIASES, ORIGINS, TIERS

ICON = {"thought": "🧠", "action": "🔧", "observation": "👁️", "reflection": "🔁", "error": "⚠️", "final": "✅"}

# ------------------------------------------------------------------ tool registry
REGISTRY = {
    "get_weather":      dict(key="weather",     fn=T.get_weather,      fallback="get_climate",   desc="live 7-day forecast (Open-Meteo API)"),
    "get_climate":      dict(key="weather",     fn=T.get_climate,      fallback=None,            desc="seasonal climate table (offline)"),
    "search_flights":   dict(key="flights",     fn=T.search_flights,   fallback="estimate_flights", desc="flight fares from origin"),
    "estimate_flights": dict(key="flights",     fn=T.estimate_flights, fallback=None,            desc="distance-based fare estimate"),
    "search_hotels":    dict(key="hotels",      fn=T.search_hotels,    fallback=None,            desc="hotels for the chosen tier"),
    "get_attractions":  dict(key="attractions", fn=T.get_attractions,  fallback=None,            desc="top attractions ranked by interests"),
    "get_restaurants":  dict(key="restaurants", fn=T.get_restaurants,  fallback=None,            desc="restaurants and average meal cost"),
    "calc_budget":      dict(key="budget",      fn=T.calc_budget,      fallback=None,            desc="python calculator sandbox: cost breakdown"),
    "convert_currency": dict(key="currency",    fn=T.convert_currency, fallback="static_rates",  desc="convert total to another currency (live FX)"),
    "static_rates":     dict(key="currency",    fn=T.static_rates,     fallback=None,            desc="offline FX table"),
}
ORDER = ["get_weather", "search_flights", "search_hotels", "get_attractions", "get_restaurants", "calc_budget", "convert_currency"]
DEPS = {"calc_budget": ["search_flights", "search_hotels", "get_attractions", "get_restaurants"],
        "convert_currency": ["calc_budget"]}
INTENT_TOOL = {"weather": "get_weather", "flights": "search_flights", "hotels": "search_hotels",
               "attractions": "get_attractions", "restaurants": "get_restaurants"}


class State(TypedDict, total=False):
    query: str
    memory: dict                      # short-term context from previous turns
    request: dict
    plan: list
    cursor: int
    results: dict
    attempts: dict
    flags: list                       # degraded-mode notes shown in the answer
    replans: int
    last: dict
    status: str
    answer: str
    itinerary: list
    trace: Annotated[list, operator.add]


def ev(kind, node, text):
    return {"kind": kind, "node": node, "text": text}


# ------------------------------------------------------------------ understanding
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
INTEREST_WORDS = {
    "beach": ["beach", "sea", "sand"], "heritage": ["heritage", "history", "historic", "fort", "palace", "monument"],
    "nature": ["nature", "trek", "hiking", "mountain", "scenic", "lake", "waterfall"],
    "food": ["food", "foodie", "cuisine", "street food"], "adventure": ["adventure", "thrill", "safari", "water sport", "rafting"],
    "spiritual": ["spiritual", "temple", "religious"], "nightlife": ["nightlife", "party", "club", "bar"],
    "shopping": ["shopping", "market", "bazaar"], "culture": ["culture", "art", "museum", "cultural"],
}
CURRENCIES = {"usd": "USD", "dollar": "USD", "dollars": "USD", "eur": "EUR", "euro": "EUR", "euros": "EUR", "aed": "AED",
              "dirham": "AED", "thb": "THB", "baht": "THB", "sgd": "SGD", "gbp": "GBP", "pound": "GBP", "pounds": "GBP"}
DEFAULT_REQ = dict(destination=None, origin="delhi", days=3, travelers=1, budget=None, tier=None,
                   interests=[], month=None, display_currency=None, intents=["full"])


def _num(s, unit):
    v = float(s.replace(",", ""))
    unit = (unit or "").lower()
    if unit == "k":
        v *= 1_000
    elif unit.startswith(("lakh", "lac")) or unit == "l":
        v *= 100_000
    return int(v)


def rule_parse(q, mem):
    """Regex/keyword understanding. Merges with the previous request so follow-ups work."""
    ql = q.lower()
    req = {**DEFAULT_REQ, **(mem or {})}
    req["interests"] = list(req.get("interests") or [])
    notes, unknown = [], None

    m = re.search(r"\bfrom\s+([a-z ]+?)(?:\s+to\b|\s+for\b|\s+with\b|\s+under\b|\s+in\b|,|\.|$)", ql)
    if m:
        o = ORIGIN_ALIASES.get(m.group(1).strip(), m.group(1).strip())
        if o in ORIGINS:
            req["origin"] = o
            ql_dest = ql.replace(m.group(0), " ")
        else:
            notes.append(f"unknown origin '{o}' ignored")
            ql_dest = ql
    else:
        ql_dest = ql
    found = [k for al, k in DEST_ALIASES.items() if re.search(rf"\b{re.escape(al)}\b", ql_dest)]
    if found:
        req["destination"] = found[0]
    else:
        m = re.search(r"(?:trip|travel|visit|holiday|vacation|tour|go|going|plan|weather|flights?|hotels?)\s+(?:to|in|for)\s+([a-z]+(?: [a-z]+)?)", ql_dest)
        if m and m.group(1) not in ("a", "the", "my", "me", "2", "3"):
            cand = m.group(1).split(" for")[0].strip()
            close = difflib.get_close_matches(cand, list(DEST_ALIASES), n=1, cutoff=0.6)
            if close:
                req["destination"] = DEST_ALIASES[close[0]]
                notes.append(f"'{cand}' looks like a typo for '{close[0]}' - auto-corrected")
            elif not mem or not mem.get("destination") or cand not in ("it", "there"):
                unknown = cand

    m = re.search(r"(\d+)\s*[- ]?\s*(?:days?|nights?)\b", ql)
    if m:
        req["days"] = int(m.group(1))
    elif "weekend" in ql:
        req["days"] = 2
    elif re.search(r"\b(a|one) week\b", ql):
        req["days"] = 7
    m = re.search(r"(?:extend|add|stay)[^\d]{0,12}(\d+)\s*(?:more|extra)?\s*days?", ql)
    if m and mem and mem.get("days"):
        req["days"] = mem["days"] + int(m.group(1))

    m = re.search(r"(\d+)\s*(?:people|persons?|travell?ers|adults|friends|pax|members)\b", ql)
    if m:
        req["travelers"] = int(m.group(1))
    elif re.search(r"couple|honeymoon", ql):
        req["travelers"] = 2
    elif re.search(r"\bsolo\b|\balone\b", ql):
        req["travelers"] = 1

    m = re.search(r"(?:budget|under|within|below|upto|up to|max(?:imum)?)[^\d₹]{0,15}(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakhs?|lacs?|l)?\b", ql) \
        or re.search(r"(?:₹|rs\.?\s*|inr\s*)([\d,]+(?:\.\d+)?)\s*(k|lakhs?|lacs?|l)?\b", ql) \
        or re.search(r"\b(\d[\d,]*(?:\.\d+)?)\s*(k|lakhs?|lacs?)\b", ql)
    if m:
        req["budget"] = _num(m.group(1), m.group(2))

    if re.search(r"cheap|backpack|economical|low[- ]cost|budget[- ]friendly|save money", ql):
        req["tier"] = "budget"
    elif re.search(r"luxur|premium|5[- ]star|lavish|splurge", ql):
        req["tier"] = "luxury"
    elif re.search(r"\bmid[- ]?range\b|\bmoderate\b", ql):
        req["tier"] = "mid"
    if mem and mem.get("tier") or req.get("tier"):
        cur = req.get("tier") or mem.get("tier")
        if re.search(r"cheaper|reduce (the )?cost|lower (the )?cost|less expensive", ql) and cur:
            req["tier"] = TIERS[max(TIERS.index(cur) - 1, 0)]
        if re.search(r"upgrade|more luxur|better hotel|nicer", ql) and cur:
            req["tier"] = TIERS[min(TIERS.index(cur) + 1, 2)]

    for i, mo in enumerate(MONTHS):
        if re.search(rf"\b{mo}\b", ql):
            req["month"] = i + 1
    for interest, words in INTEREST_WORDS.items():
        if any(w in ql for w in words) and interest not in req["interests"]:
            req["interests"].append(interest)
    for w, c in CURRENCIES.items():
        if re.search(rf"\bin {w}\b|\b{w}\b", ql):
            req["display_currency"] = c

    plan_words = r"plan|trip|itinerary|budget|package|tour|vacation|holiday|cost"
    narrow = None
    if not re.search(plan_words, ql):
        for intent, pat in [("weather", r"weather|temperature|rain|climate"), ("flights", r"flight|fly|airfare"),
                            ("hotels", r"hotel|stay|accommodation"), ("restaurants", r"restaurant|where to eat|eat"),
                            ("attractions", r"attraction|places to visit|things to do|sightseeing")]:
            if re.search(pat, ql):
                narrow = [intent]
                break
    req["intents"] = narrow or (["full"] if not (mem and mem.get("intents") and re.search(r"cheaper|extend|add|more|upgrade|change", ql)
                                                  and not re.search(plan_words, ql)) else mem["intents"])
    req["unknown_destination"] = unknown
    return req, notes


def llm_parse(q, mem):
    system = ("You extract travel requests. Fields: destination (lowercase, one of: " + ", ".join(DESTS) +
              ", or the raw name if unsupported, or null), origin (lowercase city, default 'delhi'), days (int), travelers (int), "
              "budget (total INR int or null), tier ('budget'|'mid'|'luxury'|null), interests (subset of " + ", ".join(INTEREST_WORDS) +
              "), month (1-12 or null), display_currency (ISO code or null), intents (list from: full, weather, flights, hotels, "
              "attractions, restaurants). Carry over unspecified fields from the previous request.")
    out = llm.ask_json(system, f"Previous request: {mem}\nNew message: {q}")
    req = {**DEFAULT_REQ, **(mem or {}), **{k: v for k, v in out.items() if v is not None}}
    dest = (req.get("destination") or "")
    dest = DEST_ALIASES.get(str(dest).lower(), None) or (str(dest).lower() if dest else None)
    req["unknown_destination"] = dest if dest and dest not in DESTS else None
    req["destination"] = dest if dest in DESTS else (mem or {}).get("destination")
    return req


def normalize(req):
    """Validate and repair the request. Returns (req, notes, clarification_or_None)."""
    notes = []
    if req.get("unknown_destination"):
        return req, notes, (f"I don't have data for **{req['unknown_destination'].title()}** yet. "
                            f"I can plan trips to: {', '.join(d['name'] for d in DESTS.values())}. Which one would you like?")
    if not req.get("destination"):
        return req, notes, ("Where would you like to go? I can plan trips to: " + ", ".join(d["name"] for d in DESTS.values()) + ".")
    req["origin"] = ORIGIN_ALIASES.get(req.get("origin") or "delhi", req.get("origin") or "delhi")
    if req["origin"] not in ORIGINS:
        notes.append(f"unknown origin '{req['origin']}', using Delhi")
        req["origin"] = "delhi"
    d0 = req["days"] = int(req.get("days") or 3)
    req["days"] = min(max(d0, 1), 14)
    if req["days"] != d0:
        notes.append(f"trip length {d0} days is out of range, clamped to {req['days']}")
    n0 = req["travelers"] = int(req.get("travelers") or 1)
    req["travelers"] = min(max(n0, 1), 20)
    if req["travelers"] != n0:
        notes.append(f"travellers {n0} out of range, clamped to {req['travelers']}")
    if req.get("budget") is not None and req["budget"] <= 0:
        req["budget"] = None
    req["tier"] = req.get("tier") if req.get("tier") in TIERS else "mid"
    if req.get("display_currency") not in (None, *T.STATIC_RATES):
        notes.append(f"currency {req['display_currency']} unsupported, showing INR only")
        req["display_currency"] = None
    return req, notes, None


def understand(state: State):
    q, mem = state["query"].strip(), state.get("memory") or {}
    entries = []
    if not q:
        return {"status": "clarify", "answer": "Please tell me where you'd like to travel.",
                "trace": [ev("error", "understand", "empty query")]}
    if mem:
        entries.append(ev("thought", "understand", f"Short-term memory loaded: {mem.get('destination', '?')}, "
                          f"{mem.get('days')} days, {mem.get('travelers')} traveller(s), tier={mem.get('tier')}"))
    req = None
    if llm.available():
        try:
            req = llm_parse(q, mem)
            entries.append(ev("thought", "understand", f"Parsed request with LLM ({llm.MODEL})"))
        except Exception as e:
            entries.append(ev("error", "understand", f"LLM parse failed ({type(e).__name__}) -> falling back to rule-based parser"))
    notes = []
    if req is None:
        req, notes = rule_parse(q, mem)
        entries.append(ev("thought", "understand", "Parsed request with rule-based parser"))
    req, more, clarify = normalize(req)
    for n in notes + more:
        entries.append(ev("reflection", "understand", f"Input repair: {n}"))
    if clarify:
        entries.append(ev("thought", "understand", "Cannot proceed - asking the user to clarify"))
        return {"status": "clarify", "answer": clarify, "trace": entries, "request": req}
    entries.append(ev("thought", "understand",
                      f"Request -> dest={req['destination']}, from={req['origin']}, days={req['days']}, people={req['travelers']}, "
                      f"budget={req['budget']}, tier={req['tier']}, interests={req['interests']}, intents={req['intents']}"))
    return {"request": req, "status": "ok", "trace": entries}


# ------------------------------------------------------------------ planning
def close_plan(tool_names):
    need = set(tool_names)
    changed = True
    while changed:
        changed = False
        for t in list(need):
            for dep in DEPS.get(t, []):
                if dep not in need:
                    need.add(dep)
                    changed = True
    return [t for t in ORDER if t in need]


def rule_tools(req):
    if "full" in req["intents"]:
        tools = [t for t in ORDER if t != "convert_currency"]
        if req.get("display_currency"):
            tools.append("convert_currency")
        return tools
    return [INTENT_TOOL[i] for i in req["intents"] if i in INTENT_TOOL]


def plan(state: State):
    req = state["request"]
    entries, tools_ = [], None
    if llm.available():
        try:
            catalog = "\n".join(f"- {t}: {REGISTRY[t]['desc']}" for t in ORDER)
            out = llm.ask_json("You are a planner for a travel agent. Choose the minimal set of tools needed to answer the request.\n"
                               f"Tools:\n{catalog}\nReturn {{\"tools\": [names]}}.", f"Request: {req}\nUser said: {state['query']}")
            tools_ = [t for t in out.get("tools", []) if t in ORDER]
            if not tools_:
                raise ValueError("LLM returned no valid tools")
            entries.append(ev("thought", "plan", f"LLM selected tools: {tools_}"))
        except Exception as e:
            entries.append(ev("error", "plan", f"LLM planning failed ({type(e).__name__}) -> using rule-based planner"))
    if not tools_:
        tools_ = rule_tools(req)
    steps = close_plan(tools_)
    if set(steps) != set(tools_):
        entries.append(ev("reflection", "plan", f"Added missing dependencies: {sorted(set(steps) - set(tools_))}"))
    entries.append(ev("thought", "plan", "Task decomposition: " + " -> ".join(steps)))
    return {"plan": [{"tool": t} for t in steps], "cursor": 0, "results": {}, "attempts": {}, "flags": [],
            "replans": 0, "trace": entries}


# ------------------------------------------------------------------ execution
def summarize(tool, out):
    if tool in ("get_weather", "get_climate"):
        d = out["days"][0]
        return f"{d['tmin']}-{d['tmax']}°C, rain chance {d['rain']}% (source: {out['source']})"
    if tool in ("search_flights", "estimate_flights"):
        return "; ".join(f"{o['airline']} ₹{o['price']:,.0f}" for o in out["options"]) + f" round trip/person ({out['km']} km, {out['source']})"
    if tool == "search_hotels":
        return ("; ".join(f"{o['name']} ₹{o['price']:,}/night" for o in out["options"]) or "NO RESULTS") + f" [{out['tier']}]"
    if tool == "get_attractions":
        return f"{len(out['selected'])} attractions selected ({out['matched']} match interests)"
    if tool == "get_restaurants":
        return f"{len(out['picks'])} restaurants, avg meal ₹{out['avg_meal']}"
    if tool == "calc_budget":
        return f"total ₹{out['total']:,} (₹{out['per_person']:,}/person, tier={out['tier']})"
    return f"{out['currency']} {out['converted']:,} at rate {out['rate']} ({out['source']})"


def execute(state: State):
    i = state["cursor"]
    tool = state["plan"][i]["tool"]
    reg = REGISTRY[tool]
    res = dict(state["results"])
    entries = [ev("action", "execute", f"{tool}()  - {reg['desc']}")]
    try:
        out = reg["fn"](state["request"], res)
        res[reg["key"]] = out
        entries.append(ev("observation", "execute", summarize(tool, out)))
        last = {"tool": tool, "ok": True}
    except T.ToolError as e:
        entries.append(ev("error", "execute", f"{tool} failed: {e}"))
        last = {"tool": tool, "ok": False, "error": str(e), "transient": e.transient}
    except Exception as e:  # never let an unexpected bug crash the agent
        entries.append(ev("error", "execute", f"{tool} crashed: {type(e).__name__}: {e}"))
        last = {"tool": tool, "ok": False, "error": str(e), "transient": False}
    return {"results": res, "last": last, "trace": entries}


# ------------------------------------------------------------------ reflection / self-correction
def reflect(state: State):
    last, plan_, i = state["last"], list(state["plan"]), state["cursor"]
    req, res = dict(state["request"]), state["results"]
    attempts, flags = dict(state["attempts"]), list(state["flags"])
    replans = state["replans"]
    tool, entries = last["tool"], []
    upd = {}

    if not last["ok"]:
        attempts[tool] = attempts.get(tool, 0) + 1
        fb = REGISTRY[tool]["fallback"]
        if last["transient"] and attempts[tool] == 1:
            entries.append(ev("reflection", "reflect", f"Error looks transient -> retrying {tool} once"))
        elif fb:
            plan_[i] = {"tool": fb}
            flags.append(f"{tool} unavailable -> used fallback `{fb}`")
            entries.append(ev("reflection", "reflect", f"{tool} still failing -> switching to fallback tool `{fb}`"))
        else:
            flags.append(f"{tool} unavailable, section skipped or estimated")
            entries.append(ev("reflection", "reflect", f"No fallback for {tool} -> continuing in degraded mode"))
            upd["cursor"] = i + 1
        return {**upd, "plan": plan_, "attempts": attempts, "flags": flags, "trace": entries}

    cursor = i + 1
    out = res.get(REGISTRY[tool]["key"], {})

    if tool == "search_hotels" and not out.get("options"):
        k = "hotels:incomplete"
        attempts[k] = attempts.get(k, 0) + 1
        if attempts[k] == 1:
            entries.append(ev("reflection", "reflect", "Hotel search returned no rooms (incomplete output) -> retrying"))
            cursor = i
        else:
            new = TIERS[min(TIERS.index(req["tier"]) + 1, 2)] if req["tier"] == "budget" else TIERS[TIERS.index(req["tier"]) - 1]
            entries.append(ev("reflection", "reflect", f"Still no rooms in tier '{req['tier']}' -> relaxing constraint to '{new}'"))
            req["tier"] = new
            flags.append(f"hotel tier changed to {new} (no availability)")
            cursor = i
            attempts[k] = 0
        return {"cursor": cursor, "request": req, "attempts": attempts, "flags": flags, "trace": entries}

    if tool == "get_attractions" and req["interests"] and out["matched"] == 0:
        entries.append(ev("reflection", "reflect", f"No attractions match interests {req['interests']} -> using general highlights instead"))
        flags.append("no attraction matched your interests; showing general highlights")

    if tool == "calc_budget":
        if req.get("budget") and not out["within"]:
            if req["tier"] != "budget" and replans < 3:
                new = TIERS[TIERS.index(req["tier"]) - 1]
                entries.append(ev("reflection", "reflect",
                                  f"Estimate ₹{out['total']:,} exceeds budget ₹{req['budget']:,} -> re-planning with '{new}' tier from hotel search"))
                req["tier"] = new
                hi = next(j for j, s in enumerate(plan_) if s["tool"] == "search_hotels")
                attempts = {k: v for k, v in attempts.items() if not k.endswith(":incomplete")}
                flags.append(f"downgraded to {new} tier to stay within budget")
                return {"cursor": hi, "request": req, "replans": replans + 1, "attempts": attempts, "flags": flags, "trace": entries}
            best = 0
            for d in range(req["days"] - 1, 0, -1):
                if T.compute_budget(req, res, "budget", d, use_res=False)["total"] <= req["budget"]:
                    best = d
                    break
            entries.append(ev("reflection", "reflect", f"Already at cheapest tier and still ₹{out['total'] - req['budget']:,} over budget -> will advise alternatives"))
            flags.append("OVER_BUDGET:" + str(best))
    return {"cursor": cursor, "request": req, "attempts": attempts, "flags": flags, "trace": entries}


def route(state: State):
    return "compose" if state["cursor"] >= len(state["plan"]) else "execute"


# ------------------------------------------------------------------ composing the answer
def build_itinerary(req, res):
    days = req["days"]
    attrs = res.get("attractions", {}).get("selected", [])
    weather = res.get("weather", {}).get("days", [])
    rains = [weather[min(i, len(weather) - 1)]["rain"] if weather else 0 for i in range(days)]
    per = max(1, min(3, math.ceil(len(attrs) / days))) if attrs else 0
    indoor = [a for a in attrs if a["indoor"]]
    outdoor = [a for a in attrs if not a["indoor"]]
    assigned = {}
    for i in sorted(range(days), key=lambda x: -rains[x]):  # rainiest days get indoor activities first
        pool = (indoor + outdoor) if rains[i] >= 60 else (outdoor + indoor)
        take = pool[:per]
        for a in take:
            (indoor if a in indoor else outdoor).remove(a)
        assigned[i] = take
    picks = res.get("restaurants", {}).get("picks", [])
    plan_ = []
    for i in range(days):
        w = weather[min(i, len(weather) - 1)] if weather else None
        meals = [picks[(2 * i + k) % len(picks)] for k in range(2)] if picks else []
        plan_.append({"day": i + 1, "weather": w, "activities": assigned.get(i, []), "meals": meals})
    return plan_


def money(x):
    return f"₹{x:,.0f}"


def compose(state: State):
    req, res, flags = state["request"], state["results"], state["flags"]
    d = DESTS[req["destination"]]
    full = "full" in req["intents"]
    L = []
    over = next((f for f in flags if f.startswith("OVER_BUDGET")), None)
    if full:
        L.append(f"## {req['days']}-day trip to {d['name']} · {req['travelers']} traveller(s) · from {req['origin'].title()}")
    else:
        L.append(f"## {d['name']} — {', '.join(req['intents'])}")
    if full and llm.available():
        try:
            L.append(llm.ask("Write a warm 2-sentence overview of this trip for a traveller. No lists.",
                             f"{req}\nBudget summary: {res.get('budget')}\nAttractions: {[a['name'] for a in res.get('attractions', {}).get('selected', [])]}", 200))
        except Exception:
            pass
    if "weather" in res:
        w = res["weather"]["days"]
        t0 = w[0]
        L.append(f"**🌤 Weather** ({res['weather']['source']}): {t0['tmin']}–{t0['tmax']}°C, rain chance up to {max(x['rain'] for x in w)}%.")
    if "flights" in res:
        o = T.flight_pp(res["flights"], req["tier"])
        L.append(f"**✈️ Travel:** {o['airline']} — {money(o['price'])} round trip per person (~{o['hours']} h, {res['flights']['km']} km).")
    if "hotels" in res and res["hotels"].get("options"):
        h = res["hotels"]["options"][0]
        L.append(f"**🏨 Stay ({res['hotels']['tier']}):** {h['name']} — {money(h['price'])}/night per room.")
    if "attractions" in res and not full:
        L.append("**📍 Attractions:** " + ", ".join(f"{a['name']} ({money(a['cost'])})" for a in res["attractions"]["selected"]))
    if "restaurants" in res and not full:
        L.append("**🍽 Restaurants:** " + ", ".join(f"{r['name']} ({r['cuisine']}, ~{money(r['avg'])})" for r in res["restaurants"]["picks"]))
    itin = []
    if full and "attractions" in res:
        itin = build_itinerary(req, res)
        L.append("### Day-by-day itinerary")
        for day in itin:
            w = day["weather"]
            head = f"**Day {day['day']}**"
            if w:
                head += f" — {w['tmin']}–{w['tmax']}°C, rain {w['rain']}%" + (" ☔ (indoor-friendly plan)" if w["rain"] >= 60 else "")
            L.append(head)
            if day["day"] == 1:
                L.append(f"- Arrive from {req['origin'].title()} and check in")
            for slot, a in zip(["Morning", "Afternoon", "Evening"], day["activities"]):
                L.append(f"- {slot}: {a['name']} ({'free' if a['cost'] == 0 else money(a['cost'])}, ~{a['hours']} h)")
            if not day["activities"]:
                L.append("- Free day: relax, explore on your own")
            if day["meals"]:
                L.append(f"- Eat at: {day['meals'][0]['name']} (lunch), {day['meals'][1]['name']} (dinner)")
            if day["day"] == req["days"] and req["days"] > 1:
                L.append("- Check out and head home")
    if "budget" in res:
        b = res["budget"]
        L.append("### Budget estimate")
        L.append("| Item | Cost |\n|---|---|")
        for k, v in b["items"].items():
            L.append(f"| {k} | {money(v)} |")
        L.append(f"| **Total ({b['tier']} tier)** | **{money(b['total'])}** ({money(b['per_person'])}/person) |")
        if "currency" in res:
            c = res["currency"]
            L.append(f"\n≈ **{c['currency']} {c['converted']:,}** ({c['source']})")
        if req.get("budget"):
            if b["within"]:
                L.append(f"\n✅ Within your budget of {money(req['budget'])} (₹{req['budget'] - b['total']:,} to spare).")
            elif over:
                best = int(over.split(":")[1])
                msg = f"\n⚠️ Even at the cheapest tier this costs {money(b['total'])}, above your {money(req['budget'])}. "
                msg += (f"Within budget you could do about **{best} day(s)**, or raise the budget to ~{money(b['total'])}."
                        if best else f"Consider a closer destination or raise the budget to ~{money(b['total'])}.")
                L.append(msg)
    notes = [f.replace('OVER_BUDGET:', 'over budget: ') for f in flags if not f.startswith("OVER_BUDGET")]
    if notes:
        L.append("\n> **Agent notes:** " + "; ".join(notes) + ".")
    return {"answer": "\n\n".join(L) if not itin else "\n".join(L), "itinerary": itin, "status": "done",
            "trace": [ev("final", "compose", f"Answer ready ({len(flags)} adaptation(s) made)")]}


# ------------------------------------------------------------------ graph
def build_graph():
    g = StateGraph(State)
    for name, fn in [("understand", understand), ("plan", plan), ("execute", execute), ("reflect", reflect), ("compose", compose)]:
        g.add_node(name, fn)
    g.set_entry_point("understand")
    g.add_conditional_edges("understand", lambda s: END if s.get("status") == "clarify" else "plan", {END: END, "plan": "plan"})
    g.add_edge("plan", "execute")
    g.add_edge("execute", "reflect")
    g.add_conditional_edges("reflect", route, {"execute": "execute", "compose": "compose"})
    g.add_edge("compose", END)
    return g.compile()


GRAPH = build_graph()


def run_agent(query: str, memory: dict | None = None, chaos: bool = False, on_event=None) -> dict:
    """Run one turn. Returns {answer, request (new memory), trace, results, status}."""
    T.CHAOS["enabled"] = chaos
    T.reset_chaos()
    state: dict[str, Any] = {"query": query, "memory": memory or {}, "trace": [], "results": {}}
    for update in GRAPH.stream(state, stream_mode="updates", config={"recursion_limit": 80}):
        for node, out in update.items():
            if on_event:
                on_event(node, out)
            for k, v in out.items():
                state[k] = state.get(k, []) + v if k == "trace" else v
    new_memory = {k: v for k, v in (state.get("request") or {}).items() if k != "unknown_destination"}
    if state.get("status") == "clarify":
        new_memory = memory or {}
    return {"answer": state.get("answer", ""), "memory": new_memory, "trace": state["trace"],
            "results": state.get("results", {}), "status": state.get("status")}
