#!/usr/bin/env python3
"""LoL 适配器:Oracle's Elixir CSV → 统一 match 格式;并给出评级引擎工厂。"""
import csv, os, glob
from core.engine import RatingEngine

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = {"top", "jng", "mid", "bot", "sup"}


def load(data_dir=None):
    data_dir = data_dir or os.path.join(HERE, "data")
    games = {}
    for fn in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        with open(fn, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                gid = row.get("gameid")
                if not gid:
                    continue
                g = games.setdefault(gid, {"date": row["date"], "league": row["league"],
                                           "blue": None, "red": None, "bw": None, "bp": [], "rp": []})
                side = (row.get("side") or "").lower(); pos = (row.get("position") or "").lower()
                try: won = int(row.get("result")) == 1
                except (TypeError, ValueError): won = None
                if pos == "team":
                    if side == "blue":
                        g["blue"] = row.get("teamname"); g["bw"] = won if won is not None else g["bw"]
                    elif side == "red":
                        g["red"] = row.get("teamname")
                        if won is not None and g["bw"] is None: g["bw"] = (not won)
                elif pos in ROLES:
                    nm = row.get("playername") or row.get("playerid")
                    if nm: (g["bp"] if side == "blue" else g["rp"]).append(nm)
    out = []
    for gid, g in games.items():
        if not g["blue"] or not g["red"] or g["bw"] is None: continue
        if len(g["bp"]) != 5 or len(g["rp"]) != 5: continue
        d = g["date"]
        out.append({"t": d, "date": d[:10], "year": d[:4], "league": g["league"],
                    "a": {"team": g["blue"], "ents": g["bp"]},
                    "b": {"team": g["red"], "ents": g["rp"]},
                    "a_won": bool(g["bw"])})
    out.sort(key=lambda x: x["t"])
    return out


def make_engine():
    # 融合级:0.7 选手 + 0.3 队伍;蓝方先验 +25;跨年向均值回归
    return RatingEngine(w=0.7, scale=400, side_adv=25, shrink=1.0,
                        ent=(40, 70, 15), tm=(30, 50, 10), ent_yr=0.80, tm_yr=0.75)
