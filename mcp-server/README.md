# Vault Portfolio MCP Server

Exposes portfolio data via Model Context Protocol for AI assistants.

## Tools Available

| Tool | Description |
|------|-------------|
| `get_portfolio_summary` | High-level portfolio overview (total value, accounts, gains) |
| `get_holdings` | Detailed holdings list with gains/losses |
| `get_allocation` | Portfolio allocation by sector, country, or account |
| `get_recommendations` | AI recommendations (take profit, review, rebalance) |
| `suggest_investment` | Investment suggestions for a given amount |
| `get_account_balances` | Account balances and contribution room |
| `get_performance` | Performance metrics and top/bottom performers |

## Setup

```bash
cd mcp-server
pip install -r requirements.txt
```

## Configuration

Set the API URL if not using default:

```bash
export VAULT_API_URL="http://10.43.27.109:8000/api/v1"
```

## OpenClaw Integration

Add to your OpenClaw config (`~/.openclaw/config.yaml`):

```yaml
mcp:
  servers:
    vault:
      command: python3
      args:
        - /home/Arnab/clawd/projects/vault/mcp-server/server.py
      env:
        VAULT_API_URL: "http://10.43.27.109:8000/api/v1"
```

## Usage Examples

Once configured, you can ask:

- "What's my portfolio worth right now?"
- "Show me my top performing stocks"
- "I have $5,000 CAD to invest, what should I buy?"
- "What's my allocation by sector?"
- "Any holdings I should consider selling?"
