#!/usr/bin/env python3
"""星际争霸 II(StarCraft II)适配器:PandaScore 1v1 系列 → 按小局展开(选手评级)。"""
import json, os, glob, datetime
from core.engine import RatingEngine

HERE = os.path.dirname(os.path.abspath(__file__))


def load(data_dir=None):
    data_dir = data_dir or os.path.join(HERE, "data")
    cand = glob.glob(os.path.join(data_dir, "starcraft-2*_matches.json"))
    raw = json.load(open(cand[0])) if cand else []
    today = datetime.date.today().isoformat()
    out = []
    for x in raw:
        if not (isinstance(x["s1"], int) and isinstance(x["s2"], int) and x["w"] in (1, 2)):
            continue
        if x["s1"] == x["s2"] or x["bo"] not in (1, 3, 5, 7) or not x["date"] or x["date"] > today:
            continue
        A, B = x["t1"], x["t2"]; d = x["date"]; k = 0
        for _ in range(x["s1"]):
            out.append(_row(d, x["id"], k, A, B, True)); k += 1
        for _ in range(x["s2"]):
            out.append(_row(d, x["id"], k, A, B, False)); k += 1
    out.sort(key=lambda z: z["t"])
    return out


def _row(date, mid, k, A, B, a_won):
    return {"t": f"{date}#{mid:012d}#{k}", "date": date, "year": date[:4], "league": "",
            "a": {"team": A, "ents": [A]}, "b": {"team": B, "ents": [B]}, "a_won": a_won}


def make_engine():
    return RatingEngine(w=1.0, scale=400, side_adv=0, shrink=1.0, ent=(28, 48, 8))
