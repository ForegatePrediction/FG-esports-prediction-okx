#!/usr/bin/env python3
"""
拉取使命召唤(Call of Duty)职业比赛(PandaScore 免费档)。
token 从环境变量读,绝不写进代码/聊天。King of Glory 的接口 slug 默认 "kog",
若不对,先用 --list-games 查你账号里的确切 slug,再用 --game=<slug> 覆盖。

用法:
  export PANDASCORE_TOKEN=你的token
  python3 fetch_kog.py --list-games         # 列出可用游戏和 slug(确认王者的 slug)
  python3 fetch_kog.py --test               # 只拉 1 页验证
  python3 fetch_kog.py                       # 正式拉,回溯到 2025-01-01
  python3 fetch_kog.py --game=kog 2025-01-01
"""
import os, sys, json, time, urllib.request, urllib.error

TOKEN = os.environ.get("PANDASCORE_TOKEN")
if not TOKEN:
    sys.exit("请先设置环境变量 PANDASCORE_TOKEN")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = "cod-mw"
for a in sys.argv[1:]:
    if a.startswith("--game="):
        GAME = a.split("=", 1)[1]
TEST = "--test" in sys.argv
LIST = "--list-games" in sys.argv
pos = [a for a in sys.argv[1:] if not a.startswith("--")]
CUT = pos[0] if pos else "2025-01-01"


def api(path):
    req = urllib.request.Request("https://api.pandascore.co" + path,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    for _ in range(3):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f"认证失败({e.code}):检查 token / 该游戏是否有权限")
            if e.code == 404:
                return {"__404__": True}
            time.sleep(1.5)
        except Exception:
            time.sleep(1.5)
    return None


def list_games():
    j = api("/videogames")
    if isinstance(j, list):
        for g in j:
            print(f"  id={g.get('id')}  slug={g.get('slug')!r}  name={g.get('name')!r}")
    else:
        print("无法获取:", j)


def extract(m):
    ops = m.get("opponents") or []
    if len(ops) != 2:
        return None
    t1, t2 = ops[0]["opponent"], ops[1]["opponent"]
    res = {r["team_id"]: r.get("score") for r in (m.get("results") or [])}
    return {"id": m["id"], "date": (m.get("begin_at") or "")[:10], "t1": t1["name"], "t2": t2["name"],
            "s1": res.get(t1["id"]), "s2": res.get(t2["id"]), "bo": m.get("number_of_games"),
            "w": (1 if m.get("winner_id") == t1["id"] else 2 if m.get("winner_id") == t2["id"] else None)}


def main():
    if LIST:
        return list_games()
    out_path = os.path.join(HERE, f"{GAME}_matches.json")
    rows = json.load(open(out_path)) if os.path.exists(out_path) else []
    have = set(x["id"] for x in rows); page = 1
    while page <= (1 if TEST else 400):
        batch = api(f"/{GAME}/matches/past?sort=-begin_at&page[size]=100&page[number]={page}")
        if isinstance(batch, dict) and batch.get("__404__"):
            sys.exit(f"slug '{GAME}' 不对,请先 --list-games 查正确 slug,再 --game=<slug>")
        if not batch:
            break
        added = 0
        for m in batch:
            r = extract(m)
            if not r or r["id"] in have:
                continue
            have.add(r["id"]); rows.append(r); added += 1
        json.dump(rows, open(out_path, "w"), ensure_ascii=False)
        oldest = min((x["date"] for x in rows if x["date"]), default="")
        print(f"page {page}: +{added}, total {len(rows)}, oldest {oldest}")
        if TEST:
            print("SAMPLE:", json.dumps(rows[0], ensure_ascii=False) if rows else "无数据"); break
        if oldest and oldest < CUT:
            break
        page += 1; time.sleep(0.2)
    fin = [x for x in rows if isinstance(x["s1"], int) and isinstance(x["s2"], int) and x["w"]]
    print(f"完成:总 {len(rows)},有效 {len(fin)} → {GAME}_matches.json")


if __name__ == "__main__":
    main()
