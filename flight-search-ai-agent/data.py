"""
Mock flight data for Demo Mode.

This file is ONLY data + generators. It does not contain agent logic.
A real flight API can later replace `get_mock_flights()` inside tools.py
without changing the LangGraph workflow.
"""

import math
import random
from typing import Any, Dict, List, Tuple

# City -> (region, latitude, longitude). Region "IN" means India (domestic routes).
CITY_INFO: Dict[str, Tuple[str, float, float]] = {
    # India
    "Mumbai": ("IN", 19.08, 72.88),
    "Pune": ("IN", 18.52, 73.86),
    "Delhi": ("IN", 28.61, 77.21),
    "New Delhi": ("IN", 28.61, 77.21),
    "Bengaluru": ("IN", 12.97, 77.59),
    "Bangalore": ("IN", 12.97, 77.59),
    "Hyderabad": ("IN", 17.39, 78.49),
    "Chennai": ("IN", 13.08, 80.27),
    "Kolkata": ("IN", 22.57, 88.36),
    "Goa": ("IN", 15.38, 73.83),
    "Jaipur": ("IN", 26.91, 75.79),
    "Ahmedabad": ("IN", 23.02, 72.57),
    "Kochi": ("IN", 9.93, 76.27),
    "Lucknow": ("IN", 26.85, 80.95),
    "Chandigarh": ("IN", 30.73, 76.78),
    "Indore": ("IN", 22.72, 75.86),
    "Nagpur": ("IN", 21.15, 79.09),
    "Varanasi": ("IN", 25.32, 83.01),
    "Patna": ("IN", 25.59, 85.14),
    "Guwahati": ("IN", 26.14, 91.74),
    "Srinagar": ("IN", 34.08, 74.80),
    "Bhubaneswar": ("IN", 20.30, 85.82),
    "Thiruvananthapuram": ("IN", 8.52, 76.94),
    # Gulf
    "Dubai": ("GULF", 25.20, 55.27),
    "Doha": ("GULF", 25.29, 51.53),
    "Abu Dhabi": ("GULF", 24.45, 54.38),
    # South-East Asia
    "Singapore": ("SEA", 1.35, 103.82),
    "Kuala Lumpur": ("SEA", 3.14, 101.69),
    "Bangkok": ("SEA", 13.76, 100.50),
    "Bali": ("SEA", -8.65, 115.22),
    "Phuket": ("SEA", 7.88, 98.39),
    # East Asia
    "Hong Kong": ("EASTASIA", 22.32, 114.17),
    "Tokyo": ("EASTASIA", 35.68, 139.69),
    "Seoul": ("EASTASIA", 37.57, 126.98),
    # Oceania
    "Sydney": ("OCEANIA", -33.87, 151.21),
    "Melbourne": ("OCEANIA", -37.81, 144.96),
    # Europe
    "London": ("EUROPE", 51.51, -0.13),
    "Paris": ("EUROPE", 48.86, 2.35),
    "Frankfurt": ("EUROPE", 50.11, 8.68),
    "Amsterdam": ("EUROPE", 52.37, 4.90),
    "Istanbul": ("EUROPE", 41.01, 28.98),
    # North America
    "New York": ("NA", 40.71, -74.01),
    "Los Angeles": ("NA", 34.05, -118.24),
    "San Francisco": ("NA", 37.77, -122.42),
    "Chicago": ("NA", 41.88, -87.63),
    "Toronto": ("NA", 43.65, -79.38),
    # Africa and South Asia
    "Cape Town": ("AFRICA", -33.92, 18.42),
    "Kathmandu": ("SA", 27.72, 85.32),
    "Colombo": ("SA", 6.93, 79.86),
    "Male": ("SA", 4.18, 73.51),
}

# Known city names used by the rule-based parser.
KNOWN_CITIES = list(CITY_INFO)

# Airline -> (IATA code, tier). Tier drives pricing: lcc < full < premium.
AIRLINES: Dict[str, Tuple[str, str]] = {
    "IndiGo": ("6E", "lcc"),
    "Akasa Air": ("QP", "lcc"),
    "SpiceJet": ("SG", "lcc"),
    "Air India Express": ("IX", "lcc"),
    "flydubai": ("FZ", "lcc"),
    "Air Arabia": ("G9", "lcc"),
    "Scoot": ("TR", "lcc"),
    "AirAsia": ("AK", "lcc"),
    "Air India": ("AI", "full"),
    "Vistara": ("UK", "full"),
    "Thai Airways": ("TG", "full"),
    "Malaysia Airlines": ("MH", "full"),
    "SriLankan Airlines": ("UL", "full"),
    "Turkish Airlines": ("TK", "full"),
    "Ethiopian Airlines": ("ET", "full"),
    "Air Canada": ("AC", "full"),
    "Korean Air": ("KE", "full"),
    "Emirates": ("EK", "premium"),
    "Qatar Airways": ("QR", "premium"),
    "Etihad Airways": ("EY", "premium"),
    "Singapore Airlines": ("SQ", "premium"),
    "Cathay Pacific": ("CX", "premium"),
    "Japan Airlines": ("JL", "premium"),
    "ANA": ("NH", "premium"),
    "British Airways": ("BA", "premium"),
    "Lufthansa": ("LH", "premium"),
    "Air France": ("AF", "premium"),
    "KLM": ("KL", "premium"),
    "Virgin Atlantic": ("VS", "premium"),
    "United Airlines": ("UA", "premium"),
    "American Airlines": ("AA", "premium"),
    "Delta Air Lines": ("DL", "premium"),
    "Qantas": ("QF", "premium"),
}

# Airlines that fly each region's routes to/from India.
AIRLINE_POOLS: Dict[str, List[str]] = {
    "IN": ["IndiGo", "Air India", "Akasa Air", "SpiceJet", "Vistara", "Air India Express"],
    "GULF": [
        "IndiGo", "Air India", "Air India Express", "Emirates", "Qatar Airways",
        "Etihad Airways", "flydubai", "Air Arabia",
    ],
    "SEA": [
        "IndiGo", "Air India", "Singapore Airlines", "Scoot", "AirAsia",
        "Thai Airways", "Malaysia Airlines", "Vistara",
    ],
    "EASTASIA": [
        "Air India", "Singapore Airlines", "Cathay Pacific", "Japan Airlines",
        "ANA", "Thai Airways", "Malaysia Airlines", "Korean Air",
    ],
    "OCEANIA": ["Qantas", "Air India", "Singapore Airlines", "Scoot", "Malaysia Airlines", "Thai Airways"],
    "EUROPE": [
        "Air India", "British Airways", "Lufthansa", "Air France", "KLM", "Emirates",
        "Qatar Airways", "Turkish Airlines", "Virgin Atlantic", "Etihad Airways",
    ],
    "NA": [
        "Air India", "Air Canada", "United Airlines", "American Airlines", "Emirates",
        "Qatar Airways", "Lufthansa", "British Airways", "Delta Air Lines",
    ],
    "AFRICA": ["Air India", "Emirates", "Qatar Airways", "Ethiopian Airlines", "Turkish Airlines", "Etihad Airways"],
    "SA": ["IndiGo", "Air India", "SriLankan Airlines", "Vistara", "Air India Express"],
}
# Used for cities that are not in CITY_INFO.
UNKNOWN_POOL = AIRLINE_POOLS["EUROPE"] + AIRLINE_POOLS["GULF"] + AIRLINE_POOLS["SEA"]

# Airlines that connect through their own hub on long routes.
HUB_CARRIERS = {"Emirates", "Qatar Airways", "Etihad Airways", "Turkish Airlines", "Ethiopian Airlines"}

DEPARTURE_HOURS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 1, 2]


def _distance_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance (haversine) between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _clock(minutes: int) -> str:
    minutes %= 1440
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    return f"{(hour % 12) or 12:02d}:{minute:02d} {suffix}"


def _duration_label(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _route_profile(src: str, dst: str, rng: random.Random) -> Tuple[float, str, List[str]]:
    """Return (distance_km, region, airline_pool) for a route."""
    s_info, d_info = CITY_INFO.get(src), CITY_INFO.get(dst)
    if s_info and d_info:
        km = max(150.0, _distance_km(s_info[1:], d_info[1:]))
        # The pool follows the non-Indian end of the route (destination if both are foreign).
        region = d_info[0] if d_info[0] != "IN" else s_info[0]
        return km, region, AIRLINE_POOLS[region]
    return float(rng.randint(2000, 9000)), "INTL", UNKNOWN_POOL


def _pick_stops(km: float, airline: str, rng: random.Random) -> int:
    if km < 1200:
        return 0 if rng.random() < 0.85 else 1
    if airline in HUB_CARRIERS and km > 5000:
        return 1
    if km < 2500:
        nonstop_chance = 0.85
    elif km < 5000:
        nonstop_chance = 0.75
    elif km < 9000:
        nonstop_chance = 0.35
    else:
        nonstop_chance = 0.2
    if rng.random() < nonstop_chance:
        return 0
    return 1 if rng.random() < 0.9 else 2


def _generate_flights(src: str, dst: str) -> List[Dict[str, Any]]:
    """Build a stable, route-aware flight list (same route -> same flights every run)."""
    rng = random.Random(f"{src.lower()}|{dst.lower()}")
    km, region, pool = _route_profile(src, dst, rng)
    domestic = region == "IN"

    base = 2500 + km * 4.2 if domestic else 9000 + km * 3.6
    tier_factor = {"lcc": (0.82, 0.97), "full": (1.05, 1.25), "premium": (1.2, 1.5)}
    stop_discount = {0: 1.0, 1: 0.92, 2: 0.86}

    flights: List[Dict[str, Any]] = []
    used_numbers = set()
    for _ in range(rng.randint(14, 20)):
        airline = rng.choice(pool)
        code, tier = AIRLINES[airline]
        stops = _pick_stops(km, airline, rng)

        number = f"{code} {rng.randint(100, 999)}"
        while number in used_numbers:
            number = f"{code} {rng.randint(100, 999)}"
        used_numbers.add(number)

        speed = 760 if km < 2000 else 850
        minutes = int((km * (1.1 if stops else 1.0) / speed + 0.6) * 60)
        minutes += sum(int(110 + rng.random() * 130) for _ in range(stops))
        minutes = max(45, round(minutes / 5) * 5)

        departure = rng.choice(DEPARTURE_HOURS) * 60 + rng.randrange(0, 60, 5)
        arrival_minutes = departure + minutes
        arrival = _clock(arrival_minutes)
        if arrival_minutes >= 1440:
            arrival += f" +{arrival_minutes // 1440}"

        low, high = tier_factor[tier]
        price = base * rng.uniform(low, high) * rng.uniform(0.94, 1.06) * stop_discount[stops]
        price = max(2499, int(round(price / 50) * 50))

        if tier == "premium" or (tier == "full" and not domestic):
            baggage = "30 kg"
        elif tier == "lcc":
            baggage = "15 kg" if domestic else "20 kg"
        else:
            baggage = "25 kg"
        refundable = rng.random() < {"lcc": 0.15, "full": 0.5, "premium": 0.6}[tier]

        flights.append(
            {
                "airline": airline,
                "flight_number": number,
                "departure": _clock(departure),
                "arrival": arrival,
                "duration": _duration_label(minutes),
                "stops": stops,
                "price": price,
                "baggage": baggage,
                "refundable": refundable,
            }
        )
    return flights


def _add_extras(flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add baggage / refund info to the hand-written showcase flights."""
    for flight in flights:
        _, tier = AIRLINES.get(flight["airline"], ("", "full"))
        flight.setdefault("baggage", "20 kg" if tier == "lcc" else "30 kg")
        flight.setdefault("refundable", tier != "lcc")
    return flights


def get_mock_flights(source: str, destination: str) -> List[Dict[str, Any]]:
    """
    Return mock flights for a route (10-20 options, stable between runs).

    - Pune -> Singapore is a hand-written showcase route used by the jury example.
    - Every other route is generated from real city distances, so prices, durations
      and airlines make sense (cheap short domestic hops, pricier long-haul).
    - Prices are deliberately mixed so some flights fall outside a typical budget.
    """
    src = source.strip().title()
    dst = destination.strip().title()

    # Special demo route used in the jury example.
    if src.lower() == "pune" and dst.lower() == "singapore":
        return _add_extras(
            [
                {"airline": "IndiGo", "flight_number": "6E 101", "departure": "07:30 AM", "arrival": "03:30 PM", "duration": "6h 00m", "stops": 1, "price": 24500},
                {"airline": "Scoot", "flight_number": "TR 401", "departure": "10:00 AM", "arrival": "05:30 PM", "duration": "7h 30m", "stops": 1, "price": 26000},
                {"airline": "Air India", "flight_number": "AI 503", "departure": "06:00 PM", "arrival": "03:00 AM", "duration": "8h 00m", "stops": 1, "price": 28000},
                {"airline": "Akasa Air", "flight_number": "QP 1411", "departure": "12:30 PM", "arrival": "09:45 PM", "duration": "8h 15m", "stops": 1, "price": 28750},
                {"airline": "Vistara", "flight_number": "UK 117", "departure": "09:15 AM", "arrival": "06:45 PM", "duration": "8h 30m", "stops": 1, "price": 29500},
                {"airline": "SpiceJet", "flight_number": "SG 88", "departure": "05:00 AM", "arrival": "02:15 PM", "duration": "8h 15m", "stops": 1, "price": 29990},
                {"airline": "AirAsia", "flight_number": "I5 772", "departure": "11:40 AM", "arrival": "08:10 PM", "duration": "7h 30m", "stops": 1, "price": 31200},
                {"airline": "Malaysia Airlines", "flight_number": "MH 191", "departure": "08:45 AM", "arrival": "06:20 PM", "duration": "8h 35m", "stops": 1, "price": 33450},
                {"airline": "Singapore Airlines", "flight_number": "SQ 401", "departure": "01:20 PM", "arrival": "08:50 PM", "duration": "6h 30m", "stops": 0, "price": 34800},
                {"airline": "Emirates", "flight_number": "EK 509", "departure": "02:00 AM", "arrival": "02:30 PM", "duration": "11h 30m", "stops": 1, "price": 41200},
            ]
        )

    return _generate_flights(src, dst)
