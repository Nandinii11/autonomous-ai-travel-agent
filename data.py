"""Sample travel knowledge base (fictional hotel/restaurant names, indicative prices in INR)."""

TIERS = ["budget", "mid", "luxury"]
TIER_MULT = {"budget": 0.8, "mid": 1.0, "luxury": 1.6}
BREAKFAST = {"budget": 120, "mid": 250, "luxury": 600}

ORIGINS = {
    "delhi": (28.61, 77.21), "mumbai": (19.08, 72.88), "bangalore": (12.97, 77.59),
    "kolkata": (22.57, 88.36), "chennai": (13.08, 80.27), "hyderabad": (17.39, 78.48),
    "pune": (18.52, 73.86), "ahmedabad": (23.02, 72.57), "indore": (22.72, 75.86),
    "jaipur": (26.91, 75.79),
}
ORIGIN_ALIASES = {"bengaluru": "bangalore", "new delhi": "delhi", "bombay": "mumbai", "calcutta": "kolkata"}


def season_of(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5, 6):
        return "summer"
    if month in (7, 8, 9):
        return "monsoon"
    return "autumn"


def A(name, cat, cost, hours, indoor):
    return {"name": name, "cat": cat, "cost": cost, "hours": hours, "indoor": indoor}


def R(name, cuisine, avg, level):
    return {"name": name, "cuisine": cuisine, "avg": avg, "level": level}


DESTS = {
    "goa": dict(
        name="Goa", country="India", lat=15.30, lon=74.08, intl=False, local=1200, aliases=[],
        hotels={"budget": ("Baga Backpackers Hostel", 1500), "mid": ("Calangute Palm Resort", 4000), "luxury": ("Candolim Grand Beach Resort", 11000)},
        attractions=[A("Baga Beach", "beach", 0, 3, False), A("Fort Aguada", "heritage", 0, 2, False),
                     A("Basilica of Bom Jesus", "heritage", 0, 1.5, True), A("Dudhsagar Falls", "nature", 1500, 6, False),
                     A("Water sports at Calangute", "adventure", 2000, 3, False), A("Fontainhas Latin Quarter walk", "culture", 0, 2, False),
                     A("Anjuna Flea Market", "shopping", 0, 2.5, False), A("Beach club night", "nightlife", 1500, 3, True)],
        restaurants=[R("Shack Mango", "Seafood", 400, "budget"), R("Fisherman's Wharf Cafe", "Goan", 700, "mid"),
                     R("Vinayak Family Restaurant", "Goan", 350, "budget"), R("Spice Coast Bistro", "Fusion", 1800, "luxury")],
        climate={"winter": (32, 21, 5), "summer": (34, 26, 15), "monsoon": (29, 25, 90), "autumn": (33, 24, 30)}),
    "jaipur": dict(
        name="Jaipur", country="India", lat=26.91, lon=75.79, intl=False, local=1500, aliases=["pink city"],
        hotels={"budget": ("Pink City Hostel", 1200), "mid": ("Haveli Heritage Stay", 3500), "luxury": ("Royal Palace Resort", 12000)},
        attractions=[A("Amber Fort", "heritage", 500, 3, False), A("City Palace", "heritage", 700, 2, True),
                     A("Hawa Mahal", "heritage", 200, 1, False), A("Jantar Mantar", "culture", 200, 1.5, False),
                     A("Nahargarh Fort sunset", "nature", 200, 2, False), A("Johari Bazaar shopping", "shopping", 0, 2.5, False),
                     A("Albert Hall Museum", "culture", 300, 2, True)],
        restaurants=[R("Chokhi Rasoi", "Rajasthani", 350, "budget"), R("Rawat Misthan Corner", "Snacks", 250, "budget"),
                     R("Laxmi Thali House", "Rajasthani", 800, "mid"), R("Rooftop Maharani", "Royal Rajasthani", 2200, "luxury")],
        climate={"winter": (23, 9, 3), "summer": (38, 25, 10), "monsoon": (33, 26, 60), "autumn": (31, 18, 8)}),
    "manali": dict(
        name="Manali", country="India", lat=32.24, lon=77.19, intl=False, local=2000, aliases=[],
        hotels={"budget": ("Mall Road Hostel", 1300), "mid": ("Beas Valley Lodge", 3500), "luxury": ("Himalayan Peak Resort", 9000)},
        attractions=[A("Solang Valley", "adventure", 1500, 4, False), A("Hadimba Temple", "spiritual", 0, 1, False),
                     A("Old Manali cafe walk", "culture", 0, 2, False), A("Rohtang Pass excursion", "nature", 2500, 7, False),
                     A("Vashisht hot springs", "nature", 50, 2, False), A("Tibetan Monastery", "spiritual", 0, 1.5, True),
                     A("Mall Road shopping", "shopping", 0, 2, False)],
        restaurants=[R("Johnson Cafe Style", "Trout & continental", 600, "budget"), R("Chopsticks Corner", "Tibetan", 350, "budget"),
                     R("Apple Valley Kitchen", "Himachali", 750, "mid"), R("Cedar Lodge Dining", "Multi-cuisine", 1800, "luxury")],
        climate={"winter": (8, -3, 35), "summer": (22, 10, 25), "monsoon": (22, 14, 70), "autumn": (17, 5, 10)}),
    "udaipur": dict(
        name="Udaipur", country="India", lat=24.58, lon=73.71, intl=False, local=1400, aliases=["city of lakes"],
        hotels={"budget": ("Lakeview Hostel", 1400), "mid": ("Pichola Haveli", 4200), "luxury": ("Lake Palace View Resort", 15000)},
        attractions=[A("City Palace Udaipur", "heritage", 400, 2.5, True), A("Lake Pichola boat ride", "nature", 500, 1.5, False),
                     A("Jagdish Temple", "spiritual", 0, 1, False), A("Saheliyon ki Bari", "culture", 50, 1.5, False),
                     A("Monsoon Palace sunset", "nature", 300, 2, False), A("Bagore Ki Haveli folk show", "culture", 150, 1.5, True),
                     A("Hathi Pol bazaar", "shopping", 0, 2, False)],
        restaurants=[R("Ambrai Lakeside Cafe", "Rajasthani", 700, "mid"), R("Jheel Terrace", "Indian", 350, "budget"),
                     R("Natraj Thali", "Rajasthani", 300, "budget"), R("Sunset Palace Dining", "Royal", 2500, "luxury")],
        climate={"winter": (25, 10, 3), "summer": (37, 23, 10), "monsoon": (31, 24, 65), "autumn": (31, 17, 8)}),
    "kochi": dict(
        name="Kochi", country="India", lat=9.93, lon=76.27, intl=False, local=1100, aliases=["cochin", "kerala"],
        hotels={"budget": ("Fort Kochi Homestay", 1300), "mid": ("Backwater Heritage Inn", 3200), "luxury": ("Lagoon Grand Resort", 9000)},
        attractions=[A("Chinese fishing nets", "culture", 0, 1, False), A("Fort Kochi heritage walk", "heritage", 0, 2.5, False),
                     A("Mattancherry Palace", "heritage", 50, 1.5, True), A("Kathakali performance", "culture", 400, 1.5, True),
                     A("Alleppey backwater houseboat day", "nature", 3500, 8, False), A("Marine Drive evening", "nature", 0, 1.5, False),
                     A("Spice market tour", "shopping", 0, 2, False)],
        restaurants=[R("Kayees Meals", "Kerala", 300, "budget"), R("Malabar Junction Cafe", "Seafood", 750, "mid"),
                     R("Toddy Shop Kitchen", "Kerala", 400, "budget"), R("Harbour View Dining", "Fine dining", 2000, "luxury")],
        climate={"winter": (32, 23, 10), "summer": (33, 27, 40), "monsoon": (29, 24, 90), "autumn": (31, 24, 60)}),
    "dubai": dict(
        name="Dubai", country="UAE", lat=25.20, lon=55.27, intl=True, local=4500, aliases=[],
        hotels={"budget": ("Deira Budget Inn", 4500), "mid": ("Marina City Hotel", 10000), "luxury": ("Palm Skyline Resort", 30000)},
        attractions=[A("Burj Khalifa observation deck", "culture", 4500, 2, True), A("Dubai Mall & fountain show", "shopping", 0, 3, True),
                     A("Desert safari", "adventure", 5000, 6, False), A("Old Dubai souks & abra ride", "heritage", 100, 3, False),
                     A("Jumeirah Beach", "beach", 0, 3, False), A("Museum of the Future", "culture", 3800, 2.5, True),
                     A("Dubai Marina cruise", "nightlife", 3000, 2, False)],
        restaurants=[R("Karama Kitchen", "Indian/Pakistani", 600, "budget"), R("Al Fahidi Diner", "Emirati", 900, "budget"),
                     R("Marina Grill House", "International", 2500, "mid"), R("Skyline Lounge", "Fine dining", 7000, "luxury")],
        climate={"winter": (24, 15, 10), "summer": (40, 29, 1), "monsoon": (41, 30, 1), "autumn": (35, 24, 3)}),
    "bangkok": dict(
        name="Bangkok", country="Thailand", lat=13.76, lon=100.50, intl=True, local=2500, aliases=["thailand"],
        hotels={"budget": ("Khao San Hostel", 2200), "mid": ("Sukhumvit Boutique Hotel", 5000), "luxury": ("Riverside Grand Bangkok", 15000)},
        attractions=[A("Grand Palace & Wat Phra Kaew", "heritage", 1300, 3, False), A("Wat Arun", "spiritual", 200, 1.5, False),
                     A("Chatuchak weekend market", "shopping", 0, 3, False), A("Chao Phraya river cruise", "nature", 1200, 2, False),
                     A("Thai cooking class", "culture", 2200, 3, True), A("Jim Thompson House", "culture", 500, 1.5, True),
                     A("Rooftop bar at night", "nightlife", 1800, 2.5, True), A("Street food tour Yaowarat", "food", 1500, 3, False)],
        restaurants=[R("Soi Noodle Stall", "Thai street", 250, "budget"), R("Pad Thai Corner", "Thai", 350, "budget"),
                     R("Sala Riverside", "Thai", 1300, "mid"), R("Lotus Royal Thai", "Fine dining", 4000, "luxury")],
        climate={"winter": (32, 22, 10), "summer": (36, 27, 40), "monsoon": (32, 26, 80), "autumn": (32, 25, 60)}),
    "singapore": dict(
        name="Singapore", country="Singapore", lat=1.35, lon=103.82, intl=True, local=3500, aliases=[],
        hotels={"budget": ("Little India Capsule Inn", 4500), "mid": ("Bugis City Hotel", 11000), "luxury": ("Marina Bay Grand", 28000)},
        attractions=[A("Gardens by the Bay", "nature", 2000, 3, False), A("Sentosa Island", "adventure", 3500, 6, False),
                     A("Singapore Zoo / Night Safari", "nature", 3000, 4, False), A("Chinatown & Buddha Tooth Relic Temple", "heritage", 0, 2, True),
                     A("ArtScience Museum", "culture", 3000, 2, True), A("Hawker centre food crawl", "food", 800, 2.5, False),
                     A("Orchard Road shopping", "shopping", 0, 3, True)],
        restaurants=[R("Maxwell Hawker Stall", "Hawker", 450, "budget"), R("Lau Pa Satay Corner", "Satay", 600, "budget"),
                     R("Clarke Quay Kitchen", "Peranakan", 2000, "mid"), R("Bayfront Dining Room", "Fine dining", 6500, "luxury")],
        climate={"winter": (30, 24, 60), "summer": (32, 26, 50), "monsoon": (31, 25, 50), "autumn": (31, 25, 65)}),
}

DEST_ALIASES = {}
for key, d in DESTS.items():
    DEST_ALIASES[key] = key
    for al in d["aliases"]:
        DEST_ALIASES[al] = key
