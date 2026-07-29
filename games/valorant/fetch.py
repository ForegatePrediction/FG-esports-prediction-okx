#!/usr/bin/env python3
"""
拉取 Valorant 职业比赛数据(PandaScore 免费档)。数据自带队名/比分/BO/胜方。
token 从环境变量读,绝不写进代码或聊天。

用法:
  export PANDASCORE_TOKEN=你的token      # Windows: set PANDASCORE_TOKEN=...
  python3 fetch_val.py                    # 默认回溯到 2025-07-01
  python3 fetch_val.py --test             # 只拉 1 页,验证 token/连通
  python3 fetch_val.py 2025-01-01         # 指定回溯日期
"""
import os, sys, json, time, urllib.request, urllib.error

TOKEN = os.environ.get("PANDASCORE_TOKEN")
if not TOKEN:
    sys.exit("请先设置环境变量 PANDASCORE_TOKEN(不要写进代码)")

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://api.pandascore.co/valorant/matches/past"
TEST = "--test" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CUT = args[0] if args else "2025-07-01"


def get(page):
    url = f"{BASE}?sort=-begin_at&page[size]=100&page[number]={page}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}",
                                               "Accept": "application/json"})
    for _ in range(3):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f"认证失败({e.code}):检查 token 是否正确/是否有 Valorant 权限")
            time.sleep(1.5)
        except Exception:
            time.sleep(1.5)
    return None


def extract(m):
    ops = m.get("opponents") or []
    if len(ops) != 2:
        return None
    t1 = ops[0]["opponent"]; t2 = ops[1]["opponent"]
    res = {r["team_id"]: r.get("score") for r in (m.get("results") or [])}
    s1 = res.get(t1["id"]); s2 = res.get(t2["id"])
    return {"id": m["id"], "date": (m.get("begin_at") or "")[:10],
            "t1": t1["name"], "t2": t2["name"],
            "s1": s1, "s2": s2, "bo": m.get("number_of_games"),
            "w": (1 if m.get("winner_id") == t1["id"] else 2 if m.get("winner_id") == t2["id"] else None),
            "tournament": (m.get("tournament") or {}).get("name")}


def main():
    rows = json.load(open(os.path.join(HERE, "val_matches.json"))) if os.path.exists(os.path.join(HERE, "val_matches.json")) else []
    have = set(x["id"] for x in rows)
    page = 1
    while page <= (1 if TEST else 400):
        batch = get(page)
        if not batch:
            break
        added = 0
        for m in batch:
            r = extract(m)
            if not r or r["id"] in have:
                continue
            have.add(r["id"]); rows.append(r); added += 1
        json.dump(rows, open(os.path.join(HERE, "val_matches.json"), "w"), ensure_ascii=False)
        oldest = min((x["date"] for x in rows if x["date"]), default="")
        print(f"page {page}: +{added}, total {len(rows)}, oldest {oldest}")
        if TEST:
            print("SAMPLE:", json.dumps(rows[0], ensure_ascii=False)); break
        if oldest and oldest < CUT:
            break
        page += 1
        time.sleep(0.2)
    fin = [x for x in rows if isinstance(x["s1"], int) and isinstance(x["s2"], int) and x["w"]]
    print(f"完成:总 {len(rows)},有效 {len(fin)}")


if __name__ == "__main__":
    main()
