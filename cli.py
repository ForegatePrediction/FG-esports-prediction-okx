#!/usr/bin/env python3
"""
统一 CLI —— 一套命令覆盖所有游戏。

  python3 cli.py predict  <game> "队伍A" "队伍B" [--bo N]
  python3 cli.py backtest <game>
  python3 cli.py snapshot <game>          # 由数据重建评级快照 ratings.json
  python3 cli.py list     <game> <关键词>

<game> = lol | dota2 | ...(games/ 下每个文件夹一个)
"""
import sys, os, json, importlib, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import backtest as bt
from core import predict as pred

ROOT = os.path.dirname(os.path.abspath(__file__))


def adapter(game):
    return importlib.import_module(f"games.{game}.adapter")


def cfg(game):
    return json.load(open(os.path.join(ROOT, "games", game, "config.json"), encoding="utf-8"))


def _burn(matches, c):
    b = c.get("backtest", {})
    if b.get("mode") == "last_year":
        yrs = sorted({m["year"] for m in matches}); ly = yrs[-1]
        ms = sorted(matches, key=lambda m: m["t"])
        return next(i for i, m in enumerate(ms) if m["year"] == ly)
    return int(len(matches) * b.get("frac", 0.5))


def cmd_backtest(game):
    ad = adapter(game); c = cfg(game)
    matches = ad.load()
    burn = _burn(matches, c)
    r = bt.walk_forward(matches, ad.make_engine, burn=burn)
    sr = bt.series_backtest(matches, ad.make_engine, burn=burn)
    print(f"[{c['name']}] {len(matches)} 场,暖机 {burn} / 样本外 {len(matches)-burn}\n")
    bt.print_report(c["name"], r, sr)


def cmd_snapshot(game):
    ad = adapter(game); c = cfg(game)
    matches = ad.load(); eng = ad.make_engine()
    last_roster = {}; last_date = {}; wl = {}
    for m in matches:
        eng.regress(m, m["year"])
        eng.update(m)
        for side, won in ((m["a"], m["a_won"]), (m["b"], not m["a_won"])):
            t = side["team"]
            if m["date"] >= last_date.get(t, ""):
                last_date[t] = m["date"]; last_roster[t] = side["ents"]
            w = wl.setdefault(t, [0, 0]); w[0 if won else 1] += 1
    # 活跃窗口:相对"数据最新日期"而非今天,兼容数据停更的游戏(如星际)
    ref = max(last_date.values()) if last_date else datetime.date.today().isoformat()
    cut = (datetime.date.fromisoformat(ref) - datetime.timedelta(days=150)).isoformat()
    teams = {}
    for t, roster in last_roster.items():
        w, l = wl[t]
        if (w + l) >= 8 and last_date[t] >= cut:
            teams[t] = {"rating": round(eng.team_strength(t, roster), 1),
                        "w": w, "l": l, "last_date": last_date[t]}
    p = os.path.join(ROOT, "games", game, "ratings.json")
    # 防呆:新快照过小(常见于数据抓取失败),拒绝覆盖已有的好快照
    if os.path.exists(p):
        try:
            old_n = json.load(open(p, encoding="utf-8")).get("n_teams", 0)
        except Exception:
            old_n = 0
        if old_n and len(teams) < max(5, 0.5 * old_n):
            print(f"[{c['name']}] ⚠ 拒绝写入:新快照仅 {len(teams)} 队(旧 {old_n}),疑似数据异常,保留旧快照")
            return
    out = {"game": game, "updated": datetime.date.today().isoformat(),
           "scale": c["scale"], "shrink": c["shrink"], "n_teams": len(teams),
           "teams": dict(sorted(teams.items()))}
    json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)
    print(f"[{c['name']}] 写出 {len(teams)} 队 → {p}")


def cmd_predict(game, A, B, bo, hcap, total):
    r = pred.predict(game, A, B, bo=bo, hcap=hcap, total=total)
    if "error" in r:
        return print(r["error"])
    pct = lambda x: f"{x*100:.1f}%"
    mk = r["markets"]; a, b = r["A"], r["B"]
    print(f"\n{a} vs {b}  Bo{r['bo']}  (评级 {r['ratings'][a]:.0f} / {r['ratings'][b]:.0f})")
    print(f"  ① 赛事胜负:  {a} {pct(mk['series_winner']['A'])} | {b} {pct(mk['series_winner']['B'])}")
    print(f"  ② 第一局:    {a} {pct(mk['game1_winner']['A'])} | {b} {pct(mk['game1_winner']['B'])}")
    hc = mk["map_handicap"]; print(f"  ③ 让分 {a} -{hc['line']}: {pct(hc['A_cover'])} | {b} +{hc['line']}: {pct(hc['B_cover'])}")
    tm = mk["total_maps"]; print(f"  ④ 总局数 O/U {tm['line']}: Over {pct(tm['over'])} | Under {pct(tm['under'])}")
    print("     正确比分: " + "  ".join(f"{lbl} {pct(pr)}" for lbl, _, pr in mk["correct_score"]))
    print("  ⑤ 逐局胜负(在该局被打到的前提下 / 打到该局概率):")
    for g in mk["per_game"]:
        print(f"       第{g['game']}局: {a} {pct(g['A_if_played'])} | {b} {pct(g['B_if_played'])}   (打到该局 {pct(g['reach'])})")


def main():
    if len(sys.argv) < 3:
        return print(__doc__)
    cmd, game = sys.argv[1], sys.argv[2]
    if cmd == "backtest": cmd_backtest(game)
    elif cmd == "snapshot": cmd_snapshot(game)
    elif cmd == "list":
        for t, v in pred.list_teams(game, sys.argv[3]): print(f"  {v['rating']:.0f}  {t}  {v.get('w',0)}-{v.get('l',0)}")
    elif cmd == "predict":
        p = argparse.ArgumentParser(); [p.add_argument(x) for x in ("cmd", "game", "A", "B")]
        p.add_argument("--bo", type=int, default=None); p.add_argument("--hcap", type=float, default=1.5); p.add_argument("--total", type=float, default=None)
        x = p.parse_args(); cmd_predict(game, x.A, x.B, x.bo, x.hcap, x.total)
    else: print(__doc__)


if __name__ == "__main__":
    main()
