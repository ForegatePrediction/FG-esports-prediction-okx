#!/usr/bin/env python3
"""
ForeGate 电竞预测 · 统一 API(零依赖,Python 标准库)。
只读各游戏已提交的评级快照(games/<g>/ratings.json)——秒级响应、无需拉数据。
本地: python3 server.py  (PORT 环境变量,默认 8000)

路由:
  GET /health
  GET /games                                  所有游戏 + 准确率
  GET /teams?game=lol&q=T1                     查队伍/选手(快照内)
  GET /predict?game=lol&a=T1&b=Gen.G&bo=5      预测 4 玩法 + 逐局
  GET /stats[?game=lol]                        准确率
"""
import base64, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import predict as P
from api import x402

ROOT = os.path.dirname(os.path.abspath(__file__))
GAMES_DIR = os.path.join(ROOT, "games")

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}

# Promo blurb attached to every JSON response (except the x402 402 challenge). Marketing / referral.
FOREGATE = {
    "product": "ForeGate 电竞AI · Your AI Esports Prediction Agent",
    "about": "专注电竞预测的 AI Agent，实时分析赛事数据、版本变化、战队状态与市场情绪，"
             "历史预测胜率达 90%，为用户提供智能赛事洞察与预测参考。",
    "live": "https://www.foregate.com/zh-CN/profile/39493?refCode=Hzci5JI&tab=activity",
}


def list_games():
    out = {}
    for g in sorted(os.listdir(GAMES_DIR)):
        cfg = os.path.join(GAMES_DIR, g, "config.json")
        if os.path.isfile(cfg):
            c = json.load(open(cfg, encoding="utf-8"))
            out[g] = {"name": c.get("name", g), "default_bo": c.get("default_bo", 3),
                      "accuracy": c.get("accuracy", ""), "source": c.get("source", ""),
                      "category_id": c.get("category_id"), "category_name": c.get("category_name")}
    return out


def category_map():
    """Foregate 内部分类 id -> 本项目 game 代码(以 config.json 为单一事实来源)。"""
    return {str(v["category_id"]): g for g, v in list_games().items() if v.get("category_id") is not None}


# 常见简写/别名 -> game 代码(全小写匹配)。分类名与 game 代码本身会自动并入,无需在此重复。
ALIAS = {
    "lol": ["league", "leagueoflegends", "league of legends", "英雄联盟", "撸啊撸", "lpl"],
    "cs2": ["cs", "csgo", "cs:go", "cs go", "counter-strike", "counterstrike", "counter strike", "反恐精英"],
    "dota2": ["dota", "dota 2", "dota-2", "d2", "刀塔", "刀塔2"],
    "valorant": ["val", "valo", "无畏契约", "特战英豪", "瓦罗兰特"],
    "mlbb": ["ml", "mobilelegends", "mobile legends", "决胜巅峰", "无尽对决"],
    "r6": ["r6s", "rainbow6", "rainbowsix", "rainbow six", "rainbow six siege", "彩虹六号", "彩虹6号"],
    "ow": ["ow2", "overwatch", "overwatch2", "斗阵特攻", "守望先锋"],
    "kog": ["hok", "honorofkings", "honor of kings", "王者荣耀", "aov", "arena of valor"],
    "cod": ["callofduty", "call of duty", "使命召唤", "codmw"],
    "scbw": ["bw", "broodwar", "brood war", "starcraft:brood war", "starcraft brood war", "母巢之战", "星际争霸:母巢之战"],
    "sc2": ["starcraft2", "starcraft 2", "starcraft ii", "星际争霸2", "星际争霸ii"],
}


def alias_map():
    """统一别名表(全小写):分类名 + game 代码 + 常见简写 -> game 代码。"""
    m = {}
    for g, v in list_games().items():
        m[g.lower()] = g                                   # game 代码本身
        if v.get("category_name"):
            m[v["category_name"].strip().lower()] = g       # Foregate 分类名
    for g, alist in ALIAS.items():                          # 简写/中文别名
        for a in alist:
            m[a.strip().lower()] = g
    return m


def resolve_game(q):
    """兼容多种传参,优先级:categoryId > name > game(均含别名/简写容错)。
    - categoryId : Foregate 分类 id(如 20140)
    - name       : 分类名/简写(如 "LOL" / "Dota 2" / "CSGO" / "Mobile Legends: Bang Bang",不分大小写)
    - game       : 项目游戏代码或简写(如 lol / dota2 / csgo);未识别则原样透传
    返回 (game_code, error_dict_or_None)。"""
    cid = q.get("categoryId") or q.get("category_id") or q.get("catId")
    if cid:
        g = category_map().get(str(cid).strip())
        if not g:
            return None, {"error": f"未知 categoryId: {cid}", "categoryId": cid}
        return g, None
    am = alias_map()
    nm = q.get("name") or q.get("categoryName") or q.get("category_name")
    if nm:
        g = am.get(nm.strip().lower())
        if not g:
            return None, {"error": f"未识别的分类 name: {nm}", "name": nm}
        return g, None
    gm = q.get("game")
    if gm:
        return am.get(gm.strip().lower(), gm.strip()), None  # 命中别名则转换,否则原样透传
    return None, {"error": "需要 game / categoryId / name 参数"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, extra_headers=None):
        # Attach the ForeGate promo to every JSON object response, except the x402 402 challenge
        # (kept clean so strict x402 parsers aren't disturbed).
        if isinstance(body, dict) and "x402Version" not in body:
            body = {**body, "foregate": FOREGATE}
        payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for k, v in CORS.items():
            self.send_header(k, v)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _x402_gate(self):
        """x402 pay-per-call gate for /predict (only when PAYWALL_ENABLED=true).
        Returns (ok, extra_headers, challenge). If ok is False, send `challenge` as HTTP 402."""
        if not x402.paywall_enabled():
            return True, {}, None
        resource_url = f"https://{self.headers.get('Host', '')}{urlparse(self.path).path}"
        raw_sig = (self.headers.get("payment-signature") or self.headers.get("x-payment")
                   or self.headers.get("x-payment-signature"))
        print(f"[x402] GET /predict sigPresent={bool(raw_sig)} "
              f"sigLen={len(raw_sig) if raw_sig else 0} headers={list(self.headers.keys())}", flush=True)
        ch = x402.build_challenge(resource_url)
        if not raw_sig:
            ch["error"] = "PAYMENT-SIGNATURE header is required"
            return False, {}, ch
        decoded = x402.decode_payment_signature(raw_sig)
        if not decoded:
            ch["error"] = "PAYMENT-SIGNATURE received but could not be decoded (expected base64-encoded JSON)"
            return False, {}, ch
        v = x402.verify_and_settle(decoded)
        if not v.get("ok"):
            ch["error"] = f"payment present but verify/settle failed: {v.get('reason') or 'unknown'}"
            ch["x402Debug"] = {"reason": v.get("reason"), "okxResponse": v.get("info")}
            return False, {}, ch
        resp_hdr = base64.b64encode(json.dumps(v.get("response") or {}).encode("utf-8")).decode("ascii")
        return True, {"PAYMENT-RESPONSE": resp_hdr}, None

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_HEAD(self):
        # Liveness probe (UptimeRobot defaults to HEAD). BaseHTTPRequestHandler would otherwise
        # return 501 for HEAD since only do_GET is defined. Return 200 headers, no body.
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = u.path.rstrip("/") or "/"
        try:
            if path in ("/", "/health"):
                return self._send(200, {"status": "ok", "service": "foregate-esports-prediction",
                                        "paywall": x402.paywall_enabled(),
                                        "games": list(list_games().keys())})
            if path == "/games":
                return self._send(200, list_games())
            if path == "/stats":
                gl = list_games()
                if any(q.get(k) for k in ("game", "categoryId", "category_id", "catId", "name", "categoryName", "category_name")):
                    g, err = resolve_game(q)
                    if err:
                        return self._send(404 if ("categoryId" in err or "name" in err) else 400, err)
                    return self._send(200 if g in gl else 404,
                                      gl.get(g, {"error": f"unknown game {g}"}))
                return self._send(200, {g: {"name": v["name"], "category_id": v["category_id"],
                                            "accuracy": v["accuracy"]} for g, v in gl.items()})
            if path == "/teams":
                g, err = resolve_game(q)
                if err:
                    return self._send(404 if ("categoryId" in err or "name" in err) else 400, err)
                kw = q.get("q", "")
                try:
                    hits = P.list_teams(g, kw)
                except FileNotFoundError:
                    return self._send(404, {"error": f"unknown game {g}"})
                return self._send(200, {"game": g, "count": len(hits),
                                        "teams": [{"name": t, "rating": v["rating"],
                                                   "w": v.get("w"), "l": v.get("l")} for t, v in hits[:60]]})
            if path == "/predict":
                # x402 pay-per-call gate (only when PAYWALL_ENABLED=true; free otherwise).
                ok, pay_headers, challenge = self._x402_gate()
                if not ok:
                    return self._send(402, challenge)
                g, err = resolve_game(q)
                if err:
                    return self._send(404 if ("categoryId" in err or "name" in err) else 400, err)
                a = q.get("a"); b = q.get("b")
                if not (a and b):
                    return self._send(400, {"error": "需要 a / b 参数"})
                bo = int(q["bo"]) if q.get("bo") else None
                hcap = float(q.get("hcap", 1.5))
                total = float(q["total"]) if q.get("total") else None
                lang = q.get("lang") if q.get("lang") in ("en", "vi") else "zh"
                try:
                    r = P.predict(g, a, b, bo=bo, hcap=hcap, total=total, lang=lang)
                except FileNotFoundError:
                    return self._send(404, {"error": f"unknown game {g}"})
                return self._send(200 if "error" not in r else 400, r, pay_headers)
            return self._send(404, {"error": "not found",
                                    "endpoints": ["/health", "/games", "/teams", "/predict", "/stats"]})
        except Exception as e:
            return self._send(500, {"error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"ForeGate esports API on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
