#!/usr/bin/env python3
"""CS2 适配器:PandaScore 系列数据 → 按地图展开(队伍级)。
   优先 PandaScore(csgo_matches.json);无则回退旧 bo3.gg(cs2_matches.json + cs2_teams.json)。"""
import json, os, datetime
from core.engine import RatingEngine

HERE = os.path.dirname(os.path.abspath(__file__))


def _row(date, mid, k, A, B, a_won):
    return {"t": f"{date}#{mid:012d}#{k}", "date": date, "year": date[:4], "league": "",
            "a": {"team": A, "ents": [A]}, "b": {"team": B, "ents": [B]}, "a_won": a_won}


def load(data_dir=None):
    data_dir = data_dir or os.path.join(HERE, "data")
    today = datetime.date.today().isoformat()
    out = []
    ps = os.path.join(data_dir, "csgo_matches.json")
    if os.path.exists(ps):  # PandaScore
        for x in json.load(open(ps)):
            if not (isinstance(x["s1"], int) and isinstance(x["s2"], int) and x["w"] in (1, 2)):
                continue
            if x["s1"] == x["s2"] or x["bo"] not in (1, 3, 5) or not x["date"] or x["date"] > today:
                continue
            A, B = x["t1"], x["t2"]; d = x["date"]; k = 0
            for _ in range(x["s1"]):
                out.append(_row(d, x["id"], k, A, B, True)); k += 1
            for _ in range(x["s2"]):
                out.append(_row(d, x["id"], k, A, B, False)); k += 1
    else:  # 回退:旧 bo3.gg 数据
        raw = json.load(open(os.path.join(data_dir, "cs2_matches.json")))
        tp = os.path.join(data_dir, "cs2_teams.json")
        names = json.load(open(tp)) if os.path.exists(tp) else {}
        nm = lambda i: names.get(str(i)) or f"team#{i}"
        for x in raw:
            if not (isinstance(x["s1"], int) and isinstance(x["s2"], int) and x["w"]):
                continue
            if x["s1"] == x["s2"] or x["bo"] not in (1, 3, 5) or x["date"] > today:
                continue
            A, B = nm(x["t1"]), nm(x["t2"]); d = x["date"]; k = 0
            for _ in range(x["s1"]):
                out.append(_row(d, x["id"], k, A, B, x["w"] == x["t1"])); k += 1
            for _ in range(x["s2"]):
                out.append(_row(d, x["id"], k, A, B, x["w"] != x["t1"])); k += 1
    out.sort(key=lambda z: z["t"])
    return out


def make_engine():
    return RatingEngine(w=1.0, scale=400, side_adv=0, shrink=1.0, ent=(28, 48, 8))
