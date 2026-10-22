"""
Tools that agents can call.

In Agentic AI, a "tool" is a function the agent uses to take an action
in the real (or simulated) world. This file keeps those actions separate
from planning and reasoning.
"""

import os
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List

from data import get_mock_flights


def format_inr(amount: int) -> str:
    """Format a number like 24500 as ₹24,500."""
    return f"₹{amount:,}"


def flight_search_tool(source: str, destination: str, *, quiet: bool = False) -> List[Dict[str, Any]]:
    """
    Flight Search Tool.

    Demo Mode: returns mock flights from data.py.
    Later you can replace the body of this function with a real API call
    (Amadeus, Aviationstack, etc.) and keep the same return format.
    """
    if not quiet:
        print()
        print("🔧 TOOL CALL: FLIGHT SEARCH TOOL")
        print()
        print("Searching flights...")
        print()
        print(f"Source: {source}")
        print(f"Destination: {destination}")
        print()

    flights = get_mock_flights(source, destination)

    if not quiet:
        print("✓ Flight data retrieved successfully.")
        print(f"✓ Total flights found: {len(flights)}")
        print()
    return flights


def send_email_tool(to_address: str, subject: str, body: str, *, quiet: bool = False) -> str:
    """
    Email Tool.

    - If SMTP_EMAIL and SMTP_PASSWORD are set, try to send a real email.
    - Otherwise, simulate sending (Demo Mode). This is what the jury demo uses.
    """
    if not quiet:
        print()
        print("📧 EMAIL TOOL CALL")
        print()
        print("Generating email...")
        print()
        print("✓ Email generated successfully.")

    smtp_user = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if smtp_user and smtp_password and to_address:
        try:
            message = MIMEText(body, "plain", "utf-8")
            message["From"] = smtp_user
            message["To"] = to_address
            message["Subject"] = subject

            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, [to_address], message.as_string())

            if not quiet:
                print("✓ Email sent successfully (SMTP).")
            return "sent"
        except Exception as error:
            # Never crash the demo if SMTP fails.
            if not quiet:
                print(f"⚠ Real email failed ({error}). Falling back to Demo Mode.")
                print("✓ Email sent successfully (DEMO MODE).")
            return "demo"

    if not quiet:
        print("✓ Email sent successfully (DEMO MODE).")
    return "demo"
