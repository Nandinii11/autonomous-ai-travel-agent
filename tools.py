"""External tools the agent can call.

Every tool has the signature  tool(req, results) -> dict  and raises ToolError on failure.
`results` holds the outputs of earlier tools, so tools can depend on each other.
"""
import ast
import datetime
import json
import math
import operator
import urllib.request

from data import BREAKFAST, DESTS, ORIGINS, TIER_MULT, TIERS, season_of


class ToolError(Exception):
    def __init__(self, msg, transient=False):
        super().__init__(msg)
        self.transient = transient  # transient errors are worth retrying


# ---------------------------------------------------------------- failure simulation
CHAOS = {"enabled": False, "calls": {}}


def _nth_call(name):
    CHAOS["calls"][name] = CHAOS["calls"].get(name, 0) + 1
    return CHAOS["calls"][name]


def reset_chaos():
    CHAOS["calls"].clear()


# ---------------------------------------------------------------- safe python "sandbox"
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr: str) -> float:
    """Evaluate arithmetic only (no names, calls or attributes) - a tiny code sandbox."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ToolError(f"Disallowed expression element: {type(n).__name__}")
    try:
        return ev(ast.parse(expr, mode="eval"))
    except SyntaxError as e:
        raise ToolError(f"Bad expression: {e}")


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- flights
def _flight_quote(req, source, estimate=False):
    d = DESTS[req["destination"]]
    olat, olon = ORIGINS[req["origin"]]
    km = haversine(olat, olon, d["lat"], d["lon"])
    if km < 150:
        base = 600  # short distance -> road travel
    else:
        base = (8000 + 3.0 * km) if d["intl"] else (2000 + 3.5 * km)
    rt = 2 * base
    hours = round(km / 700 + 0.7, 1)
    if estimate:
        options = [{"airline": "Estimated average fare (±15%)", "price": round(rt * 1.1, -2), "hours": hours}]
    else:
        options = [{"airline": "BudgetAir", "price": round(rt * 0.85, -2), "hours": hours + 1.0},
                   {"airline": "SkyJet", "price": round(rt, -2), "hours": hours},
                   {"airline": "Premium Wings", "price": round(rt * 1.45, -2), "hours": hours}]
    return {"options": options, "km": round(km), "source": source}


def search_flights(req, res):
    """Primary flight search (mock airline API)."""
    if CHAOS["enabled"]:
        raise ToolError("503 Service Unavailable from flight-api (simulated outage)", transient=True)
    return _flight_quote(req, "flight-api")


def estimate_flights(req, res):
    """Fallback: distance-based fare heuristic."""
    return _flight_quote(req, "distance-heuristic", estimate=True)


def flight_pp(flights, tier):
    opts = sorted(flights["options"], key=lambda o: o["price"])
    return opts[min(TIERS.index(tier), len(opts) - 1)]


# ---------------------------------------------------------------- hotels
def search_hotels(req, res):
    tier = req["tier"]
    if CHAOS["enabled"] and _nth_call("hotels") == 1:
        return {"tier": tier, "options": [], "source": "hotel-db"}  # incomplete output on purpose
    name, price = DESTS[req["destination"]]["hotels"][tier]
    return {"tier": tier, "options": [{"name": name, "price": price}], "source": "hotel-db"}


# ---------------------------------------------------------------- weather
def _climate(req, source):
    d = DESTS[req["destination"]]
    month = req.get("month") or datetime.date.today().month
    tmax, tmin, rain = d["climate"][season_of(month)]
    return {"days": [{"tmax": tmax, "tmin": tmin, "rain": rain}] * 7, "source": source}


def get_weather(req, res):
    """Live 7-day forecast from Open-Meteo (no API key needed)."""
    today = datetime.date.today()
    if req.get("month") and req["month"] != today.month:
        return _climate(req, "climatology for requested month")
    if CHAOS["enabled"] and _nth_call("weather") == 1:
        raise ToolError("Timeout contacting open-meteo (simulated)", transient=True)
    d = DESTS[req["destination"]]
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={d['lat']}&longitude={d['lon']}"
           "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&forecast_days=7&timezone=auto")
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            daily = json.load(r)["daily"]
        days = [{"tmax": round(a), "tmin": round(b), "rain": c or 0} for a, b, c in
                zip(daily["temperature_2m_max"], daily["temperature_2m_min"], daily["precipitation_probability_max"])]
    except Exception as e:
        raise ToolError(f"Weather API unreachable ({type(e).__name__})", transient=True)
    return {"days": days, "source": "open-meteo live forecast"}


def get_climate(req, res):
    """Fallback: seasonal climate table."""
    return _climate(req, "climatology table (fallback)")


# ---------------------------------------------------------------- attractions / restaurants
def rank_attractions(req):
    d = DESTS[req["destination"]]
    interests = set(req.get("interests", []))
    ranked = sorted(d["attractions"], key=lambda a: -(a["cat"] in interests))  # stable sort
    return ranked[: req["days"] * 3]


def get_attractions(req, res):
    d = DESTS[req["destination"]]
    sel = rank_attractions(req)
    interests = set(req.get("interests", []))
    matched = sum(1 for a in sel if a["cat"] in interests)
    return {"selected": sel, "matched": matched, "available": len(d["attractions"]), "source": "attraction-db"}


def get_restaurants(req, res):
    d = DESTS[req["destination"]]
    tier = req["tier"]
    same = [r for r in d["restaurants"] if r["level"] == tier]
    other = [r for r in d["restaurants"] if r["level"] != tier]
    picks = (same + other)[:4]
    avg = sum(r["avg"] for r in same) / len(same) if same else sum(r["avg"] for r in d["restaurants"]) / len(d["restaurants"])
    return {"picks": picks, "avg_meal": round(avg), "source": "restaurant-db"}


# ---------------------------------------------------------------- budget (uses the calculator sandbox)
def compute_budget(req, res, tier, days, use_res=True):
    d = DESTS[req["destination"]]
    n = req["travelers"]
    nights = max(days - 1, 1)
    rooms = math.ceil(n / 2)
    fl = res.get("flights") if use_res else None
    fl = fl or _flight_quote(req, "heuristic", estimate=True)
    flight_pp_price = flight_pp(fl, tier)["price"]
    hotel_price = d["hotels"][tier][1]
    if use_res and res.get("hotels", {}).get("options") and res["hotels"]["tier"] == tier:
        hotel_price = res["hotels"]["options"][0]["price"]
    avg_meal = res["restaurants"]["avg_meal"] if use_res and "restaurants" in res else \
        round(sum(r["avg"] for r in d["restaurants"] if r["level"] == tier) / max(1, sum(1 for r in d["restaurants"] if r["level"] == tier)))
    sel = res["attractions"]["selected"] if use_res and "attractions" in res and days == req["days"] else \
        rank_attractions({**req, "days": days})
    fees = sum(a["cost"] for a in sel)
    exprs = {
        "Flights/transport to destination": f"{flight_pp_price} * {n}",
        f"Hotel ({rooms} room x {nights} nights)": f"{hotel_price} * {nights} * {rooms}",
        "Food": f"({BREAKFAST[tier]} + 2 * {avg_meal}) * {n} * {days}",
        "Local transport": f"{d['local']} * {TIER_MULT[tier]} * {days} * {math.ceil(n / 4)}",
        "Attraction fees": f"{fees} * {n}",
    }
    items = {k: round(safe_eval(v)) for k, v in exprs.items()}
    subtotal = round(safe_eval(" + ".join(str(v) for v in items.values())))
    items["Contingency (10%)"] = round(safe_eval(f"{subtotal} * 0.10"))
    total = round(safe_eval(f"{subtotal} + {items['Contingency (10%)']}"))
    return {"items": items, "total": total, "per_person": round(total / n), "tier": tier, "days": days}


def calc_budget(req, res):
    b = compute_budget(req, res, req["tier"], req["days"])
    b["budget"] = req.get("budget")
    b["within"] = req.get("budget") is None or b["total"] <= req["budget"]
    return b


# ---------------------------------------------------------------- currency
STATIC_RATES = {"USD": 0.0119, "EUR": 0.0110, "AED": 0.0437, "THB": 0.40, "SGD": 0.0156, "GBP": 0.0094}


def convert_currency(req, res):
    cur = req["display_currency"]
    try:
        with urllib.request.urlopen(f"https://api.frankfurter.app/latest?from=INR&to={cur}", timeout=6) as r:
            rate = json.load(r)["rates"][cur]
    except Exception as e:
        raise ToolError(f"Live FX API failed for {cur} ({type(e).__name__})", transient=False)
    total = res["budget"]["total"]
    return {"currency": cur, "rate": rate, "converted": round(total * rate, 2), "source": "frankfurter live rate"}


def static_rates(req, res):
    cur = req["display_currency"]
    rate = STATIC_RATES.get(cur)
    if rate is None:
        raise ToolError(f"No offline rate for {cur}")
    return {"currency": cur, "rate": rate, "converted": round(res["budget"]["total"] * rate, 2),
            "source": "static rate table (fallback)"}
