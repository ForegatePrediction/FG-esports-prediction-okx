#!/usr/bin/env python3
"""通用走查式回测(全游戏共用)。输入:统一格式的 matches + 造引擎的工厂函数。"""
import math
from collections import defaultdict
from .series import four_markets


def _metrics():
    return {"acc": 0, "n": 0, "brier": 0.0, "ll": 0.0, "buckets": defaultdict(lambda: [0, 0.0, 0])}


def walk_forward(matches, make_engine, burn_frac=0.5, burn=None):
    matches = sorted(matches, key=lambda m: m["t"])
    N = len(matches)
    if burn is None: burn = int(N * burn_frac)
    eng = make_engine()
    M = _metrics(); a_side = 0
    for i, m in enumerate(matches):
        eng.regress(m, m["year"])
        p = eng.p_a(m)
        if i >= burn:
            o = 1.0 if m["a_won"] else 0.0
            M["n"] += 1; a_side += m["a_won"]
            if (p >= 0.5) == m["a_won"]:
                M["acc"] += 1
            M["brier"] += (p - o) ** 2
            eps = 1e-9; M["ll"] += -(o * math.log(p + eps) + (1 - o) * math.log(1 - p + eps))
            b = min(9, int(p * 10)); M["buckets"][b][0] += 1; M["buckets"][b][1] += p; M["buckets"][b][2] += m["a_won"]
        eng.update(m)
    n = M["n"] or 1
    return {"N": M["n"], "acc": M["acc"] / n, "brier": M["brier"] / n, "ll": M["ll"] / n,
            "a_rate": a_side / n, "buckets": M["buckets"], "burn": burn}


def series_backtest(matches, make_engine, burn_frac=0.5, burn=None):
    """按 (日期, 两队) 聚合成系列;用系列首局前评级预测赛事胜负。"""
    matches = sorted(matches, key=lambda m: m["t"])
    N = len(matches)
    if burn is None: burn = int(N * burn_frac)
    groups = defaultdict(list)
    for m in matches:
        key = (m["date"], tuple(sorted([m["a"]["team"], m["b"]["team"]])))
        groups[key].append(m)
    first_id = {}
    for key, gs in groups.items():
        if len(gs) >= 2:
            first_id[id(min(gs, key=lambda x: x["t"]))] = key
    eng = make_engine(); win = [0, 0]
    for i, m in enumerate(matches):
        eng.regress(m, m["year"])
        if id(m) in first_id and i >= burn:
            key = first_id[id(m)]; gs = groups[key]; A, B = key[1]
            wA = sum(1 for x in gs if (x["a"]["team"] == A and x["a_won"]) or (x["b"]["team"] == A and not x["a_won"]))
            wB = len(gs) - wA
            if wA != wB:
                # side-neutral 单局 p(A 胜)
                fm = min(gs, key=lambda x: x["t"])
                aEnts = fm["a"]["ents"] if fm["a"]["team"] == A else fm["b"]["ents"]
                bEnts = fm["a"]["ents"] if fm["a"]["team"] == B else fm["b"]["ents"]
                from .engine import expect
                p = 0.5 + (expect(eng.team_strength(A, aEnts) - eng.team_strength(B, bEnts), eng.scale) - 0.5) * eng.shrink
                bo = len(gs) if len(gs) % 2 else len(gs) + 1
                mk = four_markets(p, bo)
                win[0] += 1; win[1] += (mk["series_winner"]["A"] >= 0.5) == (wA > wB)
        eng.update(m)
    return {"N": win[0], "acc": (win[1] / win[0]) if win[0] else 0}


def print_report(name, r, sr=None):
    pct = lambda x: f"{x*100:.1f}%"
    print(f"== {name} 单局胜负 ==")
    print(f"   命中率={pct(r['acc'])}  Brier={r['brier']:.4f}  LogLoss={r['ll']:.4f}  A方胜率={pct(r['a_rate'])}  N={r['N']}")
    print("   校准表:")
    for b in range(10):
        nn, sp, w = r["buckets"][b]
        if nn:
            print(f"     [{b/10:.1f}-{(b+1)/10:.1f}) n={nn:>5} 预测={sp/nn*100:5.1f}% 实际={w/nn*100:5.1f}%")
    if sr:
        print(f"== {name} 系列赛(赛事胜负)==  命中率={pct(sr['acc'])}  N={sr['N']}")
