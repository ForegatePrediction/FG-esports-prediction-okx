#!/usr/bin/env python3
"""
下载 Oracle's Elixir 逐场比赛 CSV(免费,官方 Google Drive 每日更新)。
自动从公开文件夹列出各年份文件的最新 ID(对 ID 变动更稳健),再下载指定年份。

用法:
    python3 data/fetch.py               # 下载 2024 2025 2026
    python3 data/fetch.py 2025 2026     # 指定年份
"""
import re, sys, os, urllib.request

FOLDER_ID = "1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH"   # OE 官方 Downloads 文件夹
HERE = os.path.dirname(os.path.abspath(__file__))


def list_folder():
    """返回 {year: file_id}。"""
    url = f"https://drive.google.com/embeddedfolderview?id={FOLDER_ID}#list"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    # 结构: id="entry-FILEID" ... flip-entry-title">YEAR_LoL_...
    pairs = re.findall(r'id="entry-([^"]+)"[\s\S]{0,400}?flip-entry-title">(\d{4})_LoL', html)
    return {year: fid for fid, year in pairs}


def download(file_id, dest):
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return os.path.getsize(dest)


def main():
    years = sys.argv[1:] or ["2024", "2025", "2026"]
    folder = list_folder()
    for y in years:
        fid = folder.get(y)
        if not fid:
            print(f"[skip] {y}: 文件夹里没找到"); continue
        dest = os.path.join(HERE, f"oe_{y}.csv")
        size = download(fid, dest)
        # 校验:必须是 CSV(以 gameid 开头),不能是 HTML 错误页
        with open(dest, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(80)
        ok = head.startswith("gameid,")
        print(f"[{'ok' if ok else 'BAD'}] {y}: {size/1e6:.1f} MB  -> {dest}")
        if not ok:
            print("     ⚠️ 内容不是 CSV,可能下载失败或需要重试")


if __name__ == "__main__":
    main()
