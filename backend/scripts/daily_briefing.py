#!/usr/bin/env python3
"""
Portfolio Daily Briefing Generator

Generates a daily portfolio summary suitable for WhatsApp delivery.
Can be run standalone or called from Nix's cron system.

Usage:
    python daily_briefing.py                    # Print to stdout
    python daily_briefing.py --json             # Output raw JSON
    python daily_briefing.py --send             # Send via stdout for Nix to deliver
"""

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import httpx

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"  # Backend API (inside Docker network)
EXTERNAL_API_URL = "http://192.168.1.70:5173/api/v1"  # For external access


def fetch_briefing_data(base_url: str) -> Optional[Dict]:
    """Fetch the briefing data from the portfolio API."""
    try:
        response = httpx.get(f"{base_url}/analytics/briefing", timeout=60.0)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        # Try external URL if internal fails
        if base_url != EXTERNAL_API_URL:
            return fetch_briefing_data(EXTERNAL_API_URL)
        return None
    except Exception as e:
        print(f"Error fetching briefing data: {e}", file=sys.stderr)
        return None


def format_currency(amount: float, currency: str = "CAD") -> str:
    """Format a number as currency."""
    if amount >= 0:
        return f"${amount:,.2f}"
    else:
        return f"-${abs(amount):,.2f}"


def format_change(amount: float, pct: float) -> str:
    """Format a change with amount and percentage."""
    sign = "+" if amount >= 0 else ""
    return f"{sign}${amount:,.0f} / {sign}{pct:.2f}%"


def format_pct(pct: float) -> str:
    """Format a percentage with sign."""
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def generate_briefing_text(data: Dict) -> str:
    """Generate formatted briefing text for WhatsApp."""
    summary = data['summary']
    movers = data['movers']
    alerts = data.get('alerts', [])
    
    # Get current date
    now = datetime.now()
    date_str = now.strftime("%a %b %d")
    
    # Header
    lines = [
        f"☀️ *Portfolio Briefing — {date_str}*",
        ""
    ]
    
    # Portfolio summary
    total_value = summary['total_value_cad']
    today_change = summary['today_change_cad']
    today_pct = summary['today_change_pct']
    unrealized = summary['unrealized_gain_cad']
    unrealized_pct = summary['unrealized_gain_pct']
    
    # Today's change emoji
    if today_pct > 1:
        today_emoji = "🚀"
    elif today_pct > 0:
        today_emoji = "📈"
    elif today_pct < -1:
        today_emoji = "📉"
    elif today_pct < 0:
        today_emoji = "📊"
    else:
        today_emoji = "➡️"
    
    lines.extend([
        f"💰 *{format_currency(total_value)}* ({format_change(today_change, today_pct)}) {today_emoji}",
        f"📈 Total Gain: {format_currency(unrealized)} ({format_pct(unrealized_pct)})",
        ""
    ])
    
    # Today's movers
    gainers = movers.get('top_gainers', [])
    losers = movers.get('top_losers', [])
    
    if gainers or losers:
        lines.append("🔥 *Today's Movers*")
        
        for g in gainers[:3]:
            lines.append(f"  ▲ {g['symbol']} {format_pct(g['day_change_pct'])} ({format_currency(g['day_change_cad'])})")
        
        for l in losers[:3]:
            lines.append(f"  ▼ {l['symbol']} {format_pct(l['day_change_pct'])} ({format_currency(l['day_change_cad'])})")
        
        lines.append("")
    
    # Alerts (if any significant)
    significant_alerts = [a for a in alerts if a['severity'] in ('warning', 'alert')]
    if significant_alerts:
        lines.append("⚠️ *Alerts*")
        for alert in significant_alerts[:3]:
            lines.append(f"• {alert['message']}")
        lines.append("")
    
    # Footer
    lines.append("—")
    lines.append(f"🔗 Dashboard: 192.168.1.70:5173")
    
    return "\n".join(lines)


def generate_short_briefing(data: Dict) -> str:
    """Generate a shorter 5-line briefing."""
    summary = data['summary']
    movers = data['movers']
    
    total_value = summary['total_value_cad']
    today_change = summary['today_change_cad']
    today_pct = summary['today_change_pct']
    
    emoji = "📈" if today_pct >= 0 else "📉"
    
    lines = [
        f"{emoji} Portfolio: {format_currency(total_value)} ({format_pct(today_pct)})",
    ]
    
    gainers = movers.get('top_gainers', [])
    losers = movers.get('top_losers', [])
    
    if gainers:
        top = gainers[0]
        lines.append(f"▲ {top['symbol']} {format_pct(top['day_change_pct'])}")
    
    if losers:
        bottom = losers[0]
        lines.append(f"▼ {bottom['symbol']} {format_pct(bottom['day_change_pct'])}")
    
    return " | ".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate portfolio daily briefing")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data")
    parser.add_argument("--short", action="store_true", help="Generate short one-liner")
    parser.add_argument("--url", default=API_BASE_URL, help="API base URL")
    args = parser.parse_args()
    
    # Fetch data
    data = fetch_briefing_data(args.url)
    
    if not data:
        print("Failed to fetch portfolio data", file=sys.stderr)
        sys.exit(1)
    
    if args.json:
        print(json.dumps(data, indent=2, default=str))
    elif args.short:
        print(generate_short_briefing(data))
    else:
        print(generate_briefing_text(data))


if __name__ == "__main__":
    main()
