#!/usr/bin/env python3
"""Dota 2 适配器:PandaScore 系列数据 → 按小局展开(队伍级)。
   兼容旧 OpenDota 文件(dota_big.json)作为回退;优先 PandaScore(dota2_matches.json)。"""
import json, os, glob, datetime
from core.engine import RatingEngine

HERE = os.path.dirname(os.path.abspath(__file__))


def load(data_dir=None):
    data_dir = data_dir or os.path.join(HERE, "data")
    ps = os.path.join(data_dir, "dota2_matches.json")
    today = datetime.date.today().isoformat()
    out = []
    if os.path.exists(ps):
        for x in json.load(open(ps)):
            if not (isinstance(x["s1"], int) and isinstance(x["s2"], int) and x["w"] in (1, 2)):
                continue
            if x["s1"] == x["s2"] or x["bo"] not in (1, 2, 3, 5) or not x["date"] or x["date"] > today:
                continue
            A, B = x["t1"], x["t2"]; d = x["date"]; k = 0
            for _ in range(x["s1"]):
                out.append(_row(d, x["id"], k, A, B, True)); k += 1
            for _ in range(x["s2"]):
                out.append(_row(d, x["id"], k, A, B, False)); k += 1
    else:  # 回退:旧 OpenDota 单局数据
        cand = glob.glob(os.path.join(data_dir, "dota_big.json")) or glob.glob(os.path.join(data_dir, "dota_pro.json"))
        raw = json.load(open(cand[0])) if cand else []
        for x in raw:
            r = x.get("radiant"); dd = x.get("dire"); rw = x.get("radiant_win"); t = x.get("start_time")
            if not (r and dd and rw is not None and t):
                continue
            day = datetime.date.fromtimestamp(t).isoformat()
            if day > today:
                continue
            out.append({"t": f"{day}#{x['match_id']}", "date": day, "year": day[:4], "league": "",
                        "a": {"team": r, "ents": [r]}, "b": {"team": dd, "ents": [dd]}, "a_won": bool(rw)})
    out.sort(key=lambda z: z["t"])
    return out


def _row(date, mid, k, A, B, a_won):
    return {"t": f"{date}#{mid:012d}#{k}", "date": date, "year": date[:4], "league": "",
            "a": {"team": A, "ents": [A]}, "b": {"team": B, "ents": [B]}, "a_won": a_won}


def make_engine():
    return RatingEngine(w=1.0, scale=400, side_adv=0, shrink=1.0, ent=(28, 48, 8))
