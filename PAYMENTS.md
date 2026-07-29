# Monetizing the esports API on OKX Agent Marketplace (A2MCP · x402)

This is the **OKX paid** copy of the esports prediction API. It runs **free** (default) or
**pay-per-call** (x402) — toggled by one env var, no code change. The public/website instance
stays a separate, always-free deployment; this repo powers the paid ASP only.

## What lives where
- **Code**: `api/x402.py` (payment gate, pure stdlib) + `server.py` (wires it onto `/predict`).
  Edited locally → pushed to GitHub → auto-deployed on Render.
- **Secrets/config**: NOT in code. Set as environment variables on Render (Dashboard → service →
  **Environment**). `.env.example` lists them. Local testing can use a `.env` (gitignored).

## How it works (x402 handshake)
1. A caller hits `/predict` with no payment → server returns **HTTP 402** with `accepts`
   (price, asset `USD₮0`, your `payTo`, network `eip155:196`, both schemes: `exact`=EIP-3009,
   `upto`=Permit2).
2. The caller pays and retries with header `PAYMENT-SIGNATURE: <payload>` (base64 JSON).
3. The server sends that payload to the **OKX Payment facilitator** `/verify`; if valid it serves
   the prediction, then calls `/settle` and returns a `PAYMENT-RESPONSE` header.

Only `/predict` is gated. `/health`, `/games`, `/teams`, `/stats` stay free.

## Pricing
Default **0.01 USDT / call** (`PAY_AMOUNT=10000`, 6-decimals). Change `PAY_AMOUNT` to reprice.
(Pricing/tier decisions are still open — this is the intro default, matching the World Cup ASP.)

## Go-live steps (on Render)
1. Create a NEW web service from this repo (`render.yaml` included). Name it e.g. `foregate-esports-paid`.
2. In **Environment**, set:
   - `PAYWALL_ENABLED=true`
   - `PAY_TO_ADDRESS=<your Agentic Wallet address>`  ← an address, NOT a private key
   - `OKX_API_KEY` / `OKX_SECRET_KEY` / `OKX_PASSPHRASE` (the OKX API key triplet)
3. Save → Render redeploys. `GET /health` then shows `"paywall": true`.
4. Register this URL as a new **A2MCP ASP** on OKX Agent Marketplace, e.g.:
   - endpoint: `https://foregate-esports-paid.onrender.com/predict`
   - price: `0.01 USDT`

## Security
- The OKX key/secret/passphrase and any wallet keys must live ONLY in the Render dashboard (or a
  local gitignored `.env`). Never paste them in chat, commit them, or send them anywhere.
- OKX co-signs/settles on its side; this server never handles private keys or sends raw chain txs.

## Test locally
```bash
PAYWALL_ENABLED=false python3 server.py   # free mode (website-style)
PAYWALL_ENABLED=true  python3 server.py   # paid mode: /predict returns 402 until a valid PAYMENT-SIGNATURE
```
