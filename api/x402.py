#!/usr/bin/env python3
"""
x402 v2 pay-per-call gate for the OKX Agent Payments Protocol (A2MCP) on X Layer (eip155:196).
Calls OKX's facilitator HTTP API (/supported, /verify, /settle) with standard OKX HMAC auth.
OKX co-signs/settles (HSM) -- we never send raw chain transactions ourselves.

Auth: OK-ACCESS-{KEY,SIGN,PASSPHRASE,TIMESTAMP}. sign = base64(hmacSHA256(secret,
      timestamp + METHOD + requestPath(+query) + body)); GET body = "".

SAFE BY DEFAULT: paywall off unless PAYWALL_ENABLED=true; access DENIED unless OKX settle succeeds.
Secrets come only from env (set on the host), never hard-coded.

Pure Python standard library -- no third-party dependencies (mirrors the esports engine).
This is a faithful port of the Node reference (api/x402.mjs) from the World Cup model.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = (os.environ.get("OKX_BASE_URL") or "https://web3.okx.com").rstrip("/")
PATHS = {
    "supported": "/api/v6/pay/x402/supported",
    "verify": "/api/v6/pay/x402/verify",
    "settle": "/api/v6/pay/x402/settle",
}

CFG = {
    "enabled": os.environ.get("PAYWALL_ENABLED") == "true",
    "network": os.environ.get("PAY_NETWORK") or "eip155:196",
    "payTo": os.environ.get("OKX_X402_PAY_TO") or os.environ.get("PAY_TO_ADDRESS")
    or "0xb7338d8e84571de0d032b5fd47f31917523d0e6f",
    "amount": os.environ.get("PAY_AMOUNT") or "10000",                # 0.01 USD (6 decimals)
    "decimals": int(os.environ.get("PAY_ASSET_DECIMALS") or "6"),      # explicit, so resolvers don't guess
    "symbol": os.environ.get("PAY_ASSET_SYMBOL") or "USDT",           # human symbol hint for task systems
    "asset": os.environ.get("PAY_ASSET_CONTRACT")
    or "0x779ded0c9e1022225f8e0630b35a9b54be713736",                  # USD₮0; USDG alt in .env.example
    "eip712Name": os.environ.get("PAY_EIP712_NAME") or "USD₮0",
    "eip712Version": os.environ.get("PAY_EIP712_VERSION") or "2",
    "spenderUpto": "0x4020e7393B728A3939659E5732F87fdd8e680002",
    "spenderExact": "0x402085c248EeA27D92E8b30b2C58ed07f9E20001",
    "facilitatorOverride": os.environ.get("OKX_FACILITATOR_ADDRESS") or "",
    "apiKey": os.environ.get("OKX_API_KEY") or "",
    "secretKey": os.environ.get("OKX_SECRET_KEY") or "",
    "passphrase": os.environ.get("OKX_PASSPHRASE") or "",
}


def paywall_enabled():
    return CFG["enabled"]


def _okx_headers(method, request_path, body=""):
    """Build signed OKX headers. request_path must include any query string; body is the exact JSON string."""
    # Explicit User-Agent: OKX's edge/WAF can reject the default "Python-urllib/x.y" UA.
    h = {"Content-Type": "application/json", "User-Agent": "foregate-esports/1.0"}
    if not (CFG["apiKey"] and CFG["secretKey"] and CFG["passphrase"]):
        return h  # unsigned -> OKX rejects -> safe deny
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
    prehash = ts + method.upper() + request_path + (body or "")
    sign = base64.b64encode(
        hmac.new(CFG["secretKey"].encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii")
    h.update({
        "OK-ACCESS-KEY": CFG["apiKey"],
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-PASSPHRASE": CFG["passphrase"],
        "OK-ACCESS-TIMESTAMP": ts,
    })
    return h


def _http(method, path, obj=None, timeout=10.0):
    """One HTTP call with a hard timeout. Returns (http_ok, parsed_json). Never raises."""
    url = f"{BASE}{path}"
    body = json.dumps(obj) if obj is not None else ""
    data = body.encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=_okx_headers(method, path, body))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {}
            return True, (obj if isinstance(obj, dict) else {"_raw": obj})
    except urllib.error.HTTPError as e:  # non-2xx: still try to read the JSON error body
        try:
            raw = e.read().decode("utf-8", "replace")
            obj = json.loads(raw)
            return False, (obj if isinstance(obj, dict) else {"_raw": obj})
        except Exception:
            return False, {}
    except Exception:
        return False, {}


def _okx_get(path, timeout=10.0):
    return _http("GET", path, None, timeout)


def _okx_post(path, obj, timeout=25.0):
    return _http("POST", path, obj, timeout)


# facilitatorAddress is dynamic: GET /supported -> kinds[].extra.facilitatorAddress (cached 1h).
_fac = {"addr": CFG["facilitatorOverride"], "at": 0.0}


def get_facilitator_address():
    if CFG["facilitatorOverride"]:
        return CFG["facilitatorOverride"]
    if _fac["addr"] and (time.time() - _fac["at"] < 3600):
        return _fac["addr"]
    try:
        ok, j = _okx_get(PATHS["supported"], timeout=6.0)
        kinds = j.get("kinds") or (j.get("data") or {}).get("kinds") or []
        for k in kinds:
            f = (k or {}).get("extra", {}).get("facilitatorAddress")
            if f:
                _fac["addr"] = f
                _fac["at"] = time.time()
                return f
    except Exception:
        pass
    return _fac["addr"] or ""


def _probe_supported(timeout=8.0):
    """Raw diagnostic call to /supported that captures the exact failure (status / error class / body snippet)."""
    path = PATHS["supported"]
    req = urllib.request.Request(f"{BASE}{path}", method="GET", headers=_okx_headers("GET", path, ""))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return {"httpStatus": r.status, "bodySnippet": body[:200]}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return {"httpStatus": e.code, "error": "HTTPError", "bodySnippet": body[:200]}
    except Exception as e:
        return {"httpStatus": None, "error": type(e).__name__, "detail": str(e)[:200]}


def selftest():
    """Temporary diagnostic: shows whether OKX creds are wired and what /supported returns.
    Exposes NO secret values — only booleans + OKX's own response code/msg + the public facilitator."""
    creds_present = bool(CFG["apiKey"] and CFG["secretKey"] and CFG["passphrase"])
    probe = _probe_supported()
    ok, j = _okx_get(PATHS["supported"], timeout=8.0)
    j = j if isinstance(j, dict) else {}
    data = j.get("data") if isinstance(j.get("data"), dict) else {}
    kinds = j.get("kinds") or data.get("kinds") or []
    if not isinstance(kinds, list):
        kinds = []
    facilitator = ""
    for k in kinds:
        f = (k or {}).get("extra", {}).get("facilitatorAddress")
        if f:
            facilitator = f
            break
    return {
        "paywallEnabled": CFG["enabled"],
        "okxBaseUrl": BASE,
        "credsPresent": creds_present,
        "apiKeyLen": len(CFG["apiKey"]),           # length only, not the value
        "secretKeyLen": len(CFG["secretKey"]),
        "passphraseLen": len(CFG["passphrase"]),
        "supported": {"httpOk": ok, "code": j.get("code"), "msg": j.get("msg"),
                      "kindsCount": len(kinds), "facilitatorAddress": facilitator},
        "probe": probe,
        "facilitatorOverride": CFG["facilitatorOverride"],
    }


def build_challenge(resource_url, description="Esports Match Predictions"):
    """HTTP 402 body: x402 v2 challenge with both accepts (exact=EIP-3009, upto=Permit2)."""
    facilitator_address = get_facilitator_address()
    extra_common = {"name": CFG["eip712Name"], "version": CFG["eip712Version"],
                    "decimals": CFG["decimals"], "symbol": CFG["symbol"]}
    common = {"network": CFG["network"], "amount": CFG["amount"], "payTo": CFG["payTo"],
              "asset": CFG["asset"], "decimals": CFG["decimals"], "symbol": CFG["symbol"],
              "maxTimeoutSeconds": 300}
    return {
        "x402Version": 2,
        "error": "PAYMENT-SIGNATURE header is required",
        "resource": {"url": resource_url, "description": description, "mimeType": "application/json"},
        "accepts": [
            # exact = EIP-3009 transferWithAuthorization (no Permit2 approval needed; single fixed-price call)
            {**common, "scheme": "exact", "extra": {**extra_common, "assetTransferMethod": "eip3009"}},
            # upto = Permit2 (cap authorization / metered; needs facilitatorAddress)
            {**common, "scheme": "upto",
             "extra": {**extra_common, "assetTransferMethod": "permit2", "facilitatorAddress": facilitator_address}},
        ],
    }


def decode_payment_signature(header_val):
    """Accept the PAYMENT-SIGNATURE header as raw JSON / base64 / base64url / URL-encoded JSON."""
    if not header_val:
        return None
    if isinstance(header_val, dict):
        return header_val
    s = str(header_val).strip()
    # 1) raw JSON
    if s.startswith("{"):
        try:
            return json.loads(s)
        except Exception:
            pass
    # 2) base64 / base64url JSON
    try:
        norm = s.replace("-", "+").replace("_", "/")
        norm += "=" * (-len(norm) % 4)  # fix padding
        txt = base64.b64decode(norm).decode("utf-8", "replace")
        if "{" in txt:
            return json.loads(txt[txt.index("{"):])
    except Exception:
        pass
    # 3) URL-encoded JSON
    try:
        from urllib.parse import unquote
        return json.loads(unquote(s))
    except Exception:
        pass
    return None


def _sane(decoded):
    a = (decoded or {}).get("accepted")
    if not a or not decoded.get("payload"):
        return False
    if str(a.get("payTo", "")).lower() != CFG["payTo"].lower():
        return False
    if a.get("network") != CFG["network"]:
        return False
    if CFG["asset"] and str(a.get("asset", "")).lower() != CFG["asset"].lower():
        return False
    try:
        if int(a.get("amount") or 0) < int(CFG["amount"]):
            return False
    except Exception:
        return False
    return True


def verify_and_settle(decoded):
    """Verify then settle via OKX facilitator. Returns dict {ok, reason?, info?, response?}.
    OKX expects the standard x402 wrapper: {x402Version, paymentPayload, paymentRequirements}.
    Success is signalled by code "0" (verify: data.isValid === true)."""
    if not _sane(decoded):
        return {"ok": False, "reason": "payload failed local checks (payTo/network/asset/amount mismatch)"}
    req_body = {
        "x402Version": decoded.get("x402Version") or 2,
        "paymentPayload": decoded,                 # full decoded PAYMENT-SIGNATURE object (not base64)
        "paymentRequirements": decoded.get("accepted"),  # the single accepts entry the buyer chose
    }
    try:
        ver_ok, v = _okx_post(PATHS["verify"], req_body)
        print(f"[x402] OKX /verify httpOk={ver_ok} body={json.dumps(v)[:500]}", flush=True)
        verified = ver_ok and str(v.get("code")) == "0" and isinstance(v.get("data"), dict) \
            and (v["data"].get("isValid") is True or v["data"].get("valid") is True)
        if not verified:
            return {"ok": False,
                    "reason": f"verify rejected (code={v.get('code', '?')}{(' ' + v['msg']) if v.get('msg') else ''})",
                    "info": v}

        set_ok, s = _okx_post(PATHS["settle"], {**req_body, "syncSettle": True})
        print(f"[x402] OKX /settle httpOk={set_ok} body={json.dumps(s)[:500]}", flush=True)
        settled = set_ok and str(s.get("code")) == "0"
        d = s.get("data") or {}
        payload = decoded.get("payload") or {}
        p2 = payload.get("permit2Authorization") or {}
        return {
            "ok": settled,
            "reason": None if settled else f"settle rejected (code={s.get('code', '?')}{(' ' + s['msg']) if s.get('msg') else ''})",
            "info": None if settled else s,
            "response": {
                "status": "settled" if settled else "failed",
                "transaction": d.get("transaction") or d.get("txHash") or d.get("txnHash") or d.get("transactionHash") or "",
                "amount": (decoded.get("accepted") or {}).get("amount"),
                "payer": p2.get("from") or d.get("payer") or "",
            },
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)}
