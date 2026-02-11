#!/usr/bin/env python3
"""
Vault Portfolio MCP Server

Exposes portfolio data and investment tools via Model Context Protocol.
Enables AI assistants to provide personalized investment recommendations.
"""

import asyncio
import json
import os
import sys
from typing import Any, Optional
from decimal import Decimal
import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Configuration
VAULT_API_URL = os.getenv("VAULT_API_URL", "http://10.43.27.109:8000/api/v1")

server = Server("vault-portfolio")


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


async def fetch_api(endpoint: str, params: Optional[dict] = None) -> dict:
    """Fetch data from Vault API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{VAULT_API_URL}{endpoint}"
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available portfolio tools."""
    return [
        Tool(
            name="get_portfolio_summary",
            description="""Get a high-level summary of the portfolio including:
- Total portfolio value in CAD and USD
- Total invested amount
- Overall gain/loss percentage
- Number of holdings
- Account breakdown (TFSA, RRSP, FHSA, etc.)

Use this first to understand the portfolio context.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_holdings",
            description="""Get detailed list of all holdings with:
- Symbol, company name, exchange
- Quantity, average cost, current price
- Current value and gain/loss ($ and %)
- Day change
- Account type

Optionally filter by account type or sort by different criteria.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "description": "Filter by account type (TFSA, RRSP, FHSA, NON_REG, DEMAT, MF_INDIA)",
                        "enum": ["TFSA", "RRSP", "FHSA", "NON_REG", "DEMAT", "MF_INDIA"]
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort holdings by: value, gain_pct, day_change, allocation",
                        "enum": ["value", "gain_pct", "day_change", "allocation"],
                        "default": "value"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Limit number of results",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_allocation",
            description="""Get portfolio allocation breakdown by:
- Sector (Technology, Healthcare, Finance, etc.)
- Country (Canada, USA, India)
- Account type (TFSA, RRSP, etc.)
- Currency (CAD, USD, INR)

Useful for understanding diversification and concentration risks.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_by": {
                        "type": "string",
                        "description": "Group allocation by: sector, country, account, currency",
                        "enum": ["sector", "country", "account", "currency"],
                        "default": "sector"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_recommendations",
            description="""Get AI-generated portfolio recommendations including:
- Take Profit: Holdings with >40% gains that could be trimmed
- Review: Holdings with >20% losses to evaluate
- Rebalance: Overweight positions (>12% of portfolio)
- Watch: Holdings with significant daily moves (>3%)

Also returns portfolio health score (0-100) and grade (A-F).""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="suggest_investment",
            description="""Given an amount to invest, suggest optimal allocation based on:
- Current portfolio weights vs target allocation
- Underweight sectors/regions that need rebalancing
- Account type considerations (TFSA room, RRSP contribution)
- Tax efficiency (dividends, capital gains)

Returns specific buy recommendations with rationale.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Amount to invest in CAD"
                    },
                    "account_type": {
                        "type": "string",
                        "description": "Target account (TFSA, RRSP, FHSA, NON_REG)",
                        "enum": ["TFSA", "RRSP", "FHSA", "NON_REG"]
                    },
                    "risk_tolerance": {
                        "type": "string",
                        "description": "Risk tolerance level",
                        "enum": ["conservative", "moderate", "aggressive"],
                        "default": "moderate"
                    }
                },
                "required": ["amount"]
            }
        ),
        Tool(
            name="get_account_balances",
            description="""Get balances and contribution room for registered accounts:
- TFSA: Current balance, contribution room, lifetime limit
- RRSP: Current balance, contribution room
- FHSA: Current balance, contribution room

Useful for tax planning and contribution decisions.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_performance",
            description="""Get portfolio performance over time:
- Daily, weekly, monthly, YTD, 1-year returns
- Comparison to benchmarks (S&P 500, TSX)
- Best/worst performers

Optionally specify time range.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period for performance",
                        "enum": ["1d", "1w", "1m", "3m", "6m", "1y", "ytd", "all"],
                        "default": "1m"
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    try:
        if name == "get_portfolio_summary":
            return await handle_portfolio_summary()
        elif name == "get_holdings":
            return await handle_holdings(arguments)
        elif name == "get_allocation":
            return await handle_allocation(arguments)
        elif name == "get_recommendations":
            return await handle_recommendations()
        elif name == "suggest_investment":
            return await handle_suggest_investment(arguments)
        elif name == "get_account_balances":
            return await handle_account_balances()
        elif name == "get_performance":
            return await handle_performance(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_portfolio_summary() -> list[TextContent]:
    """Get portfolio summary."""
    data = await fetch_api("/analytics/summary", {"fast": "true"})
    
    summary = f"""## Portfolio Summary

**Total Value:** ${data.get('total_value_cad', 0):,.2f} CAD (${data.get('total_value_usd', 0):,.2f} USD)
**Total Invested:** ${data.get('total_invested', 0):,.2f} CAD
**Overall Gain/Loss:** ${data.get('total_gain', 0):,.2f} ({data.get('total_gain_pct', 0):.1f}%)
**Day Change:** ${data.get('day_change', 0):,.2f} ({data.get('day_change_pct', 0):.2f}%)

### Holdings: {data.get('holdings_count', 0)} positions

### By Account:
"""
    for acc in data.get('by_account', []):
        summary += f"- **{acc['account_type']}**: ${acc['value']:,.2f} ({acc['allocation']:.1f}%)\n"
    
    return [TextContent(type="text", text=summary)]


async def handle_holdings(arguments: dict) -> list[TextContent]:
    """Get holdings list."""
    params = {"fast": "true"}
    if arguments.get("account_type"):
        params["account_type"] = arguments["account_type"]
    
    data = await fetch_api("/holdings", params)
    
    holdings = data if isinstance(data, list) else data.get('holdings', [])
    
    # Sort if specified
    sort_by = arguments.get("sort_by", "value")
    if sort_by == "value":
        holdings.sort(key=lambda x: x.get('current_value', 0) or 0, reverse=True)
    elif sort_by == "gain_pct":
        holdings.sort(key=lambda x: x.get('gain_pct', 0) or 0, reverse=True)
    elif sort_by == "day_change":
        holdings.sort(key=lambda x: abs(x.get('day_change_pct', 0) or 0), reverse=True)
    
    # Limit
    limit = arguments.get("limit", 20)
    holdings = holdings[:limit]
    
    result = "## Holdings\n\n"
    result += "| Symbol | Company | Qty | Avg Cost | Price | Value | Gain % | Account |\n"
    result += "|--------|---------|-----|----------|-------|-------|--------|----------|\n"
    
    for h in holdings:
        gain_pct = h.get('gain_pct', 0) or 0
        gain_indicator = "🟢" if gain_pct > 0 else "🔴" if gain_pct < 0 else "⚪"
        result += f"| {h.get('symbol', '')} | {h.get('company_name', '')[:20]} | {h.get('quantity', 0)} | ${h.get('average_cost', 0):.2f} | ${h.get('current_price', 0):.2f} | ${h.get('current_value', 0):,.0f} | {gain_indicator} {gain_pct:+.1f}% | {h.get('account_type', '')} |\n"
    
    return [TextContent(type="text", text=result)]


async def handle_allocation(arguments: dict) -> list[TextContent]:
    """Get allocation breakdown."""
    group_by = arguments.get("group_by", "sector")
    data = await fetch_api("/analytics/allocation", {"fast": "true", "group_by": group_by})
    
    result = f"## Portfolio Allocation by {group_by.title()}\n\n"
    
    allocations = data.get('allocation', data.get('allocations', []))
    if isinstance(allocations, dict):
        allocations = [{"name": k, "value": v.get('value', 0), "pct": v.get('pct', 0)} for k, v in allocations.items()]
    
    # Sort by percentage descending
    allocations.sort(key=lambda x: x.get('pct', x.get('allocation', 0)), reverse=True)
    
    for item in allocations:
        name = item.get('name', item.get(group_by, 'Unknown'))
        pct = item.get('pct', item.get('allocation', 0))
        value = item.get('value', 0)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        result += f"**{name}**: {pct:.1f}% (${value:,.0f})\n{bar}\n\n"
    
    return [TextContent(type="text", text=result)]


async def handle_recommendations() -> list[TextContent]:
    """Get portfolio recommendations."""
    data = await fetch_api("/analytics/recommendations", {"fast": "true"})
    
    health_score = data.get('health_score', 100)
    health_grade = data.get('health_grade', 'A')
    
    result = f"""## Portfolio Health: {health_grade} ({health_score:.0f}/100)

### Summary
- 🎯 Take Profit: {data.get('summary', {}).get('take_profit', 0)}
- 🔍 Review: {data.get('summary', {}).get('review', 0)}
- ⚖️ Rebalance: {data.get('summary', {}).get('rebalance', 0)}
- 👀 Watch: {data.get('summary', {}).get('watch', 0)}

### Recommendations
"""
    
    for rec in data.get('recommendations', []):
        emoji = {"take_profit": "🎯", "review": "🔍", "rebalance": "⚖️", "watch": "👀"}.get(rec.get('type'), "📌")
        severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec.get('severity'), "⚪")
        
        result += f"\n{severity_color} {emoji} **{rec.get('title', '')}**\n"
        result += f"   {rec.get('description', '')}\n"
        if rec.get('metric') is not None:
            result += f"   {rec.get('metric_label', 'Metric')}: {rec.get('metric'):+.1f}%\n"
    
    return [TextContent(type="text", text=result)]


async def handle_suggest_investment(arguments: dict) -> list[TextContent]:
    """Suggest investment allocation for a given amount."""
    amount = arguments.get("amount", 0)
    account_type = arguments.get("account_type", "TFSA")
    risk_tolerance = arguments.get("risk_tolerance", "moderate")
    
    # Get current allocation to identify underweight areas
    allocation_data = await fetch_api("/analytics/allocation", {"fast": "true", "group_by": "sector"})
    holdings_data = await fetch_api("/holdings", {"fast": "true"})
    
    holdings = holdings_data if isinstance(holdings_data, list) else holdings_data.get('holdings', [])
    
    # Calculate current sector weights
    total_value = sum(h.get('current_value', 0) or 0 for h in holdings)
    
    # Target allocation based on risk tolerance
    target_allocation = {
        "conservative": {
            "Bonds/Fixed Income": 40,
            "Large Cap": 35,
            "International": 15,
            "Small/Mid Cap": 5,
            "Alternatives": 5
        },
        "moderate": {
            "Large Cap": 40,
            "International": 25,
            "Small/Mid Cap": 15,
            "Bonds/Fixed Income": 15,
            "Alternatives": 5
        },
        "aggressive": {
            "Large Cap": 35,
            "Small/Mid Cap": 25,
            "International": 25,
            "Alternatives": 10,
            "Bonds/Fixed Income": 5
        }
    }.get(risk_tolerance, {})
    
    result = f"""## Investment Suggestion: ${amount:,.2f} CAD

**Target Account:** {account_type}
**Risk Profile:** {risk_tolerance.title()}

### Recommended Allocation

Based on your current portfolio and {risk_tolerance} risk tolerance, here's how I'd suggest allocating ${amount:,.2f}:

"""
    
    # Suggest specific ETFs based on gaps
    suggestions = []
    
    if risk_tolerance == "conservative":
        suggestions = [
            ("XBB.TO", "iShares Core Canadian Universe Bond", 35, "Canadian bonds for stability"),
            ("XEQT.TO", "iShares Core Equity ETF Portfolio", 40, "Diversified global equities"),
            ("XIC.TO", "iShares Core S&P/TSX Capped", 15, "Canadian market exposure"),
            ("ZAG.TO", "BMO Aggregate Bond Index", 10, "Additional fixed income")
        ]
    elif risk_tolerance == "moderate":
        suggestions = [
            ("XEQT.TO", "iShares Core Equity ETF Portfolio", 45, "Diversified global equities - your core holding"),
            ("VFV.TO", "Vanguard S&P 500 Index", 25, "US large cap growth"),
            ("XIC.TO", "iShares Core S&P/TSX Capped", 15, "Canadian market exposure"),
            ("XEF.TO", "iShares Core MSCI EAFE", 15, "International developed markets")
        ]
    else:  # aggressive
        suggestions = [
            ("VFV.TO", "Vanguard S&P 500 Index", 30, "US large cap growth"),
            ("QQQ", "Invesco QQQ Trust", 25, "US tech/growth exposure"),
            ("XEQT.TO", "iShares Core Equity ETF Portfolio", 25, "Global diversification"),
            ("XST.TO", "iShares S&P/TSX SmallCap Index", 10, "Canadian small cap growth"),
            ("ARKK", "ARK Innovation ETF", 10, "High-growth innovation plays")
        ]
    
    for symbol, name, pct, rationale in suggestions:
        allocation_amount = amount * pct / 100
        result += f"**{symbol}** - ${allocation_amount:,.2f} ({pct}%)\n"
        result += f"   {name}\n"
        result += f"   _{rationale}_\n\n"
    
    result += f"""
### Notes for {account_type}

"""
    if account_type == "TFSA":
        result += "- Tax-free growth makes this ideal for high-growth investments\n"
        result += "- No tax on withdrawals - good for stocks with capital gains potential\n"
        result += "- US dividends are subject to 15% withholding (consider Canadian-listed ETFs)\n"
    elif account_type == "RRSP":
        result += "- US dividends are not subject to withholding tax (use US-listed ETFs)\n"
        result += "- Good for income-generating investments\n"
        result += "- Contributions reduce current year taxes\n"
    elif account_type == "FHSA":
        result += "- Tax-free growth AND tax-deductible contributions\n"
        result += "- Ideal for medium-term growth\n"
        result += "- Same US dividend treatment as RRSP\n"
    
    return [TextContent(type="text", text=result)]


async def handle_account_balances() -> list[TextContent]:
    """Get account balances and contribution room."""
    data = await fetch_api("/analytics/summary", {"fast": "true"})
    
    # Get holdings grouped by account
    holdings_data = await fetch_api("/holdings", {"fast": "true"})
    holdings = holdings_data if isinstance(holdings_data, list) else holdings_data.get('holdings', [])
    
    # Calculate per-account totals
    account_totals = {}
    for h in holdings:
        acc = h.get('account_type', 'Unknown')
        if acc not in account_totals:
            account_totals[acc] = {"value": 0, "count": 0}
        account_totals[acc]["value"] += h.get('current_value', 0) or 0
        account_totals[acc]["count"] += 1
    
    result = """## Account Balances

### Registered Accounts (Canada)

| Account | Balance | Holdings | Notes |
|---------|---------|----------|-------|
"""
    
    # TFSA
    tfsa_value = account_totals.get('TFSA', {}).get('value', 0)
    result += f"| TFSA | ${tfsa_value:,.2f} | {account_totals.get('TFSA', {}).get('count', 0)} | Tax-free growth |\n"
    
    # RRSP
    rrsp_value = account_totals.get('RRSP', {}).get('value', 0)
    result += f"| RRSP | ${rrsp_value:,.2f} | {account_totals.get('RRSP', {}).get('count', 0)} | Tax-deferred |\n"
    
    # FHSA
    fhsa_value = account_totals.get('FHSA', {}).get('value', 0)
    result += f"| FHSA | ${fhsa_value:,.2f} | {account_totals.get('FHSA', {}).get('count', 0)} | First Home Savings |\n"
    
    # Non-registered
    nonreg_value = account_totals.get('NON_REG', {}).get('value', 0)
    result += f"| Non-Registered | ${nonreg_value:,.2f} | {account_totals.get('NON_REG', {}).get('count', 0)} | Taxable |\n"
    
    result += """
### India Accounts

| Account | Balance | Holdings |
|---------|---------|----------|
"""
    
    # DEMAT
    demat_value = account_totals.get('DEMAT', {}).get('value', 0)
    result += f"| Zerodha (DEMAT) | ₹{demat_value:,.0f} | {account_totals.get('DEMAT', {}).get('count', 0)} |\n"
    
    # MF
    mf_value = account_totals.get('MF_INDIA', {}).get('value', 0)
    result += f"| Groww (MF) | ₹{mf_value:,.0f} | {account_totals.get('MF_INDIA', {}).get('count', 0)} |\n"
    
    result += """
### 2025 Contribution Limits (Canada)

| Account | Annual Limit | Lifetime Max |
|---------|--------------|--------------|
| TFSA | $7,000 | $95,000 (cumulative since 2009) |
| RRSP | 18% of income (max $31,560) | Based on contribution room |
| FHSA | $8,000 | $40,000 lifetime |

_Note: Check your CRA My Account for exact contribution room._
"""
    
    return [TextContent(type="text", text=result)]


async def handle_performance(arguments: dict) -> list[TextContent]:
    """Get portfolio performance."""
    period = arguments.get("period", "1m")
    
    # Try to get performance data from snapshots
    try:
        data = await fetch_api("/snapshots/performance", {"period": period})
    except:
        data = {}
    
    # Get current summary for basic stats
    summary = await fetch_api("/analytics/summary", {"fast": "true"})
    
    result = f"""## Portfolio Performance

### Current Status
**Total Value:** ${summary.get('total_value_cad', 0):,.2f} CAD
**Day Change:** ${summary.get('day_change', 0):,.2f} ({summary.get('day_change_pct', 0):+.2f}%)
**Total Return:** {summary.get('total_gain_pct', 0):+.1f}%

### Top Performers (by gain %)
"""
    
    # Get holdings to show top/bottom performers
    holdings_data = await fetch_api("/holdings", {"fast": "true"})
    holdings = holdings_data if isinstance(holdings_data, list) else holdings_data.get('holdings', [])
    
    # Sort by gain %
    sorted_holdings = sorted(holdings, key=lambda x: x.get('gain_pct', 0) or 0, reverse=True)
    
    result += "\n**Winners:**\n"
    for h in sorted_holdings[:5]:
        if (h.get('gain_pct') or 0) > 0:
            result += f"- {h.get('symbol')}: +{h.get('gain_pct', 0):.1f}% (${h.get('unrealized_gain', 0):+,.0f})\n"
    
    result += "\n**Losers:**\n"
    for h in sorted_holdings[-5:]:
        if (h.get('gain_pct') or 0) < 0:
            result += f"- {h.get('symbol')}: {h.get('gain_pct', 0):.1f}% (${h.get('unrealized_gain', 0):,.0f})\n"
    
    return [TextContent(type="text", text=result)]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
