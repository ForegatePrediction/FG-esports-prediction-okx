#!/usr/bin/env python3
"""通用轻量预测(全游戏共用)。读 games/<game>/config.json + ratings.json,零训练秒出 4 玩法。"""
import json, os
from .engine import expect
from .series import four_markets, per_game_markets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(game):
    gdir = os.path.join(ROOT, "games", game)
    cfg = json.load(open(os.path.join(gdir, "config.json"), encoding="utf-8"))
    snap = json.load(open(os.path.join(gdir, "ratings.json"), encoding="utf-8"))
    return cfg, snap["teams"]


def _find(teams, name):
    if name in teams:
        return name
    c = [t for t in teams if name.lower() in t.lower() or t.lower() in name.lower()]
    return max(c, key=lambda t: teams[t].get("w", 0) + teams[t].get("l", 0)) if c else None


def _reasons(A, B, rA, rB, mk, bo, lang):
    d = round(abs(rA - rB)); p = mk["single_map"]; sw = mk["series_winner"]
    favN, favP = (A, sw["A"]) if sw["A"] >= sw["B"] else (B, sw["B"])
    strong = A if rA >= rB else B
    tm = mk["total_maps"]; longish = tm["over"] >= tm["under"]
    pc = lambda x: f"{round(x*100)}%"
    hl = mk["map_handicap"]["line"]; tl = tm["line"]
    # 强队自己净胜 >hl 局(-hl 让分/横扫)的概率:从比分分布取该方大比分获胜之和
    sl = "A" if strong == A else "B"
    coverFav = sum(pr for sc, w, pr in mk["correct_score"]
                   if w == sl and abs(int(sc.split("-")[0]) - int(sc.split("-")[1])) > hl)
    if lang == "en":
        return {
            "winner": [f"{A} rating {round(rA)} vs {B} {round(rB)} (gap {d})",
                       f"Bo{bo} amplifies the stronger side → {favN} {pc(favP)}"],
            "game1": [f"Single-map: {A} {pc(p)} / {B} {pc(1-p)}"],
            "handicap": [f"P({strong} covers -{hl}, i.e. wins by ≥2 maps) = {pc(coverFav)}"],
            "total": [f"{'Tends to go long / more maps' if longish else 'Tends to be short'} — Over {tl} {pc(tm['over'])}"],
        }
    if lang == "vi":
        return {
            "winner": [f"{A} điểm {round(rA)} vs {B} {round(rB)} (chênh {d})",
                       f"Bo{bo} khuếch đại lợi thế đội mạnh → nghiêng về {favN} {pc(favP)}"],
            "game1": [f"Tỷ lệ thắng 1 ván: {A} {pc(p)} / {B} {pc(1-p)}"],
            "handicap": [f"P({strong} thắng cách biệt ≥2 ván, chấp -{hl}) = {pc(coverFav)}"],
            "total": [f"{'Xu hướng kéo dài / nhiều ván' if longish else 'Xu hướng ít ván / kết thúc nhanh'} — Tài {tl} {pc(tm['over'])}"],
        }
    return {
        "winner": [f"{A} 评级 {round(rA)} vs {B} {round(rB)}(相差 {d} 分)",
                   f"Bo{bo} 系列赛放大强队优势 → 倾向 {favN} {pc(favP)}"],
        "game1": [f"单图胜率:{A} {pc(p)} / {B} {pc(1-p)}"],
        "handicap": [f"{strong} 净胜 ≥2 局(-{hl},横扫/大比分)概率 {pc(coverFav)}"],
        "total": [f"{'偏向打满 / 局数偏多' if longish else '偏向速战 / 局数偏少'} — 大于 {tl} 概率 {pc(tm['over'])}"],
    }


def predict(game, A, B, bo=None, hcap=1.5, total=None, lang="zh"):
    cfg, teams = _load(game)
    a, b = _find(teams, A), _find(teams, B)
    if not a or not b:
        return {"error": f"未找到:{A if not a else B}", "missing": A if not a else B}
    bo = bo or cfg.get("default_bo", 3)
    exact = (A == a and B == b)
    rA, rB = teams[a]["rating"], teams[b]["rating"]
    p = 0.5 + (expect(rA - rB, cfg.get("scale", 400)) - 0.5) * cfg.get("shrink", 1.0)
    mk = four_markets(p, bo, hcap_line=hcap, total_line=total)
    mk["per_game"] = per_game_markets(p, bo)
    return {"game": game, "A": a, "B": b, "bo": bo, "lang": lang, "matched_exact": exact,
            "ratings": {a: rA, b: rB}, "markets": mk,
            "reasons": _reasons(a, b, rA, rB, mk, bo, lang)}


def list_teams(game, kw):
    _, teams = _load(game)
    kw = kw.lower()
    hits = sorted([(t, v) for t, v in teams.items() if kw in t.lower()], key=lambda x: -x[1]["rating"])
    return hits
