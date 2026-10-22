"""
Mock flight data for Demo Mode.

This file is ONLY data + a generator. It does not contain agent logic.
A real flight API can later replace `get_mock_flights()` inside tools.py
without changing the LangGraph workflow.
"""

from typing import List, Dict, Any


# Known city names used by the rule-based parser (longest names first).
KNOWN_CITIES = [
    "New Delhi",
    "Singapore",
    "Kuala Lumpur",
    "Abu Dhabi",
    "New York",
    "Los Angeles",
    "San Francisco",
    "Hong Kong",
    "Cape Town",
    "Mumbai",
    "Pune",
    "Delhi",
    "Bengaluru",
    "Bangalore",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Goa",
    "Jaipur",
    "Ahmedabad",
    "Kochi",
    "Dubai",
    "Doha",
    "London",
    "Paris",
    "Tokyo",
    "Bangkok",
    "Bali",
    "Sydney",
    "Melbourne",
    "Toronto",
    "Chicago",
    "Frankfurt",
    "Amsterdam",
    "Istanbul",
    "Male",
    "Kathmandu",
    "Colombo",
]


def _base_price(source: str, destination: str) -> int:
    """Pick a stable starting price so the same route always looks the same."""
    text = f"{source.lower()}|{destination.lower()}"
    seed = sum(ord(ch) for ch in text)
    return 18000 + (seed % 8000)


def get_mock_flights(source: str, destination: str) -> List[Dict[str, Any]]:
    """
    Return at least 10 realistic mock flights for a route.

    Prices are mixed on purpose:
    - some are cheap (within a typical student budget)
    - some are expensive (so the analysis agent can reject them)
    """
    src = source.strip().title()
    dst = destination.strip().title()

    # Special demo route used in the jury example.
    if src.lower() == "pune" and dst.lower() == "singapore":
        return [
            {
                "airline": "IndiGo",
                "flight_number": "6E 101",
                "departure": "07:30 AM",
                "arrival": "03:30 PM",
                "duration": "6h 00m",
                "stops": 1,
                "price": 24500,
            },
            {
                "airline": "Scoot",
                "flight_number": "TR 401",
                "departure": "10:00 AM",
                "arrival": "05:30 PM",
                "duration": "7h 30m",
                "stops": 1,
                "price": 26000,
            },
            {
                "airline": "Air India",
                "flight_number": "AI 503",
                "departure": "06:00 PM",
                "arrival": "03:00 AM",
                "duration": "8h 00m",
                "stops": 1,
                "price": 28000,
            },
            {
                "airline": "Akasa Air",
                "flight_number": "QP 1411",
                "departure": "12:30 PM",
                "arrival": "09:45 PM",
                "duration": "8h 15m",
                "stops": 1,
                "price": 28750,
            },
            {
                "airline": "Vistara",
                "flight_number": "UK 117",
                "departure": "09:15 AM",
                "arrival": "06:45 PM",
                "duration": "8h 30m",
                "stops": 1,
                "price": 29500,
            },
            {
                "airline": "SpiceJet",
                "flight_number": "SG 88",
                "departure": "05:00 AM",
                "arrival": "02:15 PM",
                "duration": "8h 15m",
                "stops": 1,
                "price": 29990,
            },
            {
                "airline": "AirAsia",
                "flight_number": "I5 772",
                "departure": "11:40 AM",
                "arrival": "08:10 PM",
                "duration": "7h 30m",
                "stops": 1,
                "price": 31200,
            },
            {
                "airline": "Malaysia Airlines",
                "flight_number": "MH 191",
                "departure": "08:45 AM",
                "arrival": "06:20 PM",
                "duration": "8h 35m",
                "stops": 1,
                "price": 33450,
            },
            {
                "airline": "Singapore Airlines",
                "flight_number": "SQ 401",
                "departure": "01:20 PM",
                "arrival": "08:50 PM",
                "duration": "6h 30m",
                "stops": 0,
                "price": 34800,
            },
            {
                "airline": "Emirates",
                "flight_number": "EK 509",
                "departure": "02:00 AM",
                "arrival": "02:30 PM",
                "duration": "11h 30m",
                "stops": 1,
                "price": 41200,
            },
        ]

    # Generic but stable mock inventory for any other city pair.
    start = _base_price(src, dst)
    templates = [
        ("IndiGo", "6E 211", "06:45 AM", "02:15 PM", "6h 30m", 1, start - 1500),
        ("Air India", "AI 430", "08:10 AM", "04:40 PM", "7h 30m", 1, start + 800),
        ("Vistara", "UK 955", "09:30 AM", "05:00 PM", "6h 30m", 0, start + 4200),
        ("SpiceJet", "SG 312", "11:00 AM", "07:45 PM", "7h 45m", 1, start - 2200),
        ("AirAsia", "I5 618", "01:15 PM", "09:20 PM", "7h 05m", 1, start + 1100),
        ("Emirates", "EK 214", "03:40 PM", "02:10 AM", "9h 30m", 1, start + 9800),
        ("Scoot", "TR 18", "05:20 PM", "01:50 AM", "7h 30m", 1, start - 400),
        ("Singapore Airlines", "SQ 422", "07:00 AM", "02:10 PM", "6h 10m", 0, start + 7600),
        ("Qatar Airways", "QR 556", "10:25 PM", "08:55 AM", "9h 30m", 1, start + 6400),
        ("Thai Airways", "TG 401", "12:50 PM", "08:40 PM", "6h 50m", 1, start + 2500),
        ("Malaysia Airlines", "MH 194", "04:05 AM", "12:35 PM", "7h 30m", 1, start + 3100),
        ("Akasa Air", "QP 1502", "02:30 PM", "10:55 PM", "7h 25m", 1, start - 900),
    ]

    flights = []
    for airline, number, dep, arr, duration, stops, price in templates:
        flights.append(
            {
                "airline": airline,
                "flight_number": number,
                "departure": dep,
                "arrival": arr,
                "duration": duration,
                "stops": stops,
                "price": max(8999, int(price)),
            }
        )
    return flights
