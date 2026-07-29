#!/usr/bin/env python3
"""系列赛 4 玩法数学(全游戏共用)。由单局胜率 p 展开:赛事胜负/第一局/局数让分/总局数。"""
from collections import defaultdict


def _comb(n, r):
    if r < 0 or r > n:
        return 0
    x = 1.0
    for i in range(r):
        x = x * (n - i) / (i + 1)
    return x


def series_scores(p, best_of):
    k = (best_of + 1) // 2
    q = 1 - p
    out = [("A", k, l, _comb(k - 1 + l, l) * p ** k * q ** l) for l in range(k)]
    out += [("B", l, k, _comb(k - 1 + l, l) * q ** k * p ** l) for l in range(k)]
    return out


def per_game_markets(p, best_of):
    """每一局(地图)的胜负 + 该局被打到的概率。
    近似每局独立、单局胜率=p:
      - reach   : 系列赛打到第 k 局的概率(前 k-1 局未分出胜负)
      - A_if_played / B_if_played : 在第 k 局被打的前提下,双方胜率(= p / 1-p)
      - A_uncond: 无条件"A 赢下第 k 局"概率(= reach × p),供需要该口径的玩法
    """
    K = (best_of + 1) // 2
    q = 1 - p
    out = []
    for k in range(1, best_of + 1):
        reach = 0.0
        for i in range(0, k):           # 前 k-1 局中 A 赢 i 局
            if i <= K - 1 and (k - 1 - i) <= K - 1:
                reach += _comb(k - 1, i) * p ** i * q ** (k - 1 - i)
        out.append({"game": k, "reach": reach,
                    "A_if_played": p, "B_if_played": q,
                    "A_uncond": reach * p, "B_uncond": reach * q})
    return out


def four_markets(p, best_of, hcap_line=1.5, total_line=None):
    if total_line is None:
        total_line = 2.5 if best_of == 3 else 4.5
    sc = series_scores(p, best_of)
    winA = sum(s[3] for s in sc if s[0] == "A")
    coverA = sum(s[3] for s in sc if (s[1] - s[2]) > hcap_line)
    maps = defaultdict(float)
    for s in sc:
        maps[s[1] + s[2]] += s[3]
    over = sum(v for m, v in maps.items() if m > total_line)
    return {
        "single_map": p,
        "series_winner": {"A": winA, "B": 1 - winA},
        "game1_winner": {"A": p, "B": 1 - p},
        "map_handicap": {"line": hcap_line, "A_cover": coverA, "B_cover": 1 - coverA},
        "total_maps": {"line": total_line, "over": over, "under": 1 - over,
                       "dist": {m: maps[m] for m in sorted(maps)}},
        "correct_score": [(f"{s[1]}-{s[2]}", s[0], s[3]) for s in sorted(sc, key=lambda x: -x[3])],
    }
