#!/usr/bin/env python3
"""
每日刷新:逐游戏重拉数据 -> 重建 games/<g>/ratings.json 快照。
- 免费源(lol/dota2/cs2)无需 token;PandaScore 8 个游戏需环境变量 PANDASCORE_TOKEN。
- 容错:单个游戏失败不影响其它;数据文件不入库(gitignore),只提交更新后的 ratings.json。
用法:python3 refresh.py [game ...]   # 不带参数则刷新全部
"""
import os, sys, subprocess, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# 每个游戏:fetch 命令(相对 games/<g>/fetch.py)+ 采集产出的文件名(会被移进 data/)+ 是否需要 token
SPEC = {
    "lol":      {"args": [],                 "outputs": ["oe_2024.csv", "oe_2025.csv", "oe_2026.csv"], "token": False},
    "dota2":    {"args": [],                 "outputs": ["dota2_matches.json"],                         "token": True},
    "cs2":      {"args": [],                 "outputs": ["csgo_matches.json"],                          "token": True},
    "valorant": {"args": [],                 "outputs": ["val_matches.json"],                           "token": True},
    "kog":      {"args": [],                 "outputs": ["kog_matches.json"],                           "token": True},
    "mlbb":     {"args": [],                 "outputs": ["mlbb_matches.json"],                          "token": True},
    "r6":       {"args": ["--game=r6siege"], "outputs": ["r6siege_matches.json"],                       "token": True},
    "ow":       {"args": [],                 "outputs": ["ow_matches.json"],                            "token": True},
    "cod":      {"args": ["--game=codmw"],   "outputs": ["codmw_matches.json"],                         "token": True},
    "scbw":     {"args": [],                 "outputs": ["starcraft-brood-war_matches.json"],           "token": True},
    "sc2":      {"args": [],                 "outputs": ["starcraft-2_matches.json"],                   "token": True},
}


def fetch_script(gdir):
    for name in os.listdir(gdir):
        if name.startswith("fetch") and name.endswith(".py"):
            return os.path.join(gdir, name)
    return None


def refresh(game, spec):
    gdir = os.path.join(ROOT, "games", game)
    if spec["token"] and not os.environ.get("PANDASCORE_TOKEN"):
        print(f"[skip] {game}: 无 PANDASCORE_TOKEN"); return "skip"
    fs = fetch_script(gdir)
    if not fs:
        print(f"[skip] {game}: 找不到 fetch 脚本"); return "skip"
    try:
        subprocess.run([PY, fs] + spec["args"], cwd=gdir, check=True, timeout=1200)
        # 采集产出在 games/<g>/ 根目录,移进 data/(适配器从 data/ 读)
        ddir = os.path.join(gdir, "data"); os.makedirs(ddir, exist_ok=True)
        for f in spec["outputs"]:
            src = os.path.join(gdir, f)
            if os.path.exists(src):
                shutil.move(src, os.path.join(ddir, f))
        subprocess.run([PY, os.path.join(ROOT, "cli.py"), "snapshot", game], check=True, timeout=600)
        print(f"[ok] {game}")
        return "ok"
    except Exception as e:
        print(f"[fail] {game}: {str(e)[:120]}")
        return "fail"


def main():
    games = sys.argv[1:] or list(SPEC.keys())
    result = {g: refresh(g, SPEC[g]) for g in games if g in SPEC}
    print("\n汇总:", result)
    # 只要有一个成功就算这次刷新有产出;全失败才非零退出
    if result and all(v != "ok" for v in result.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
