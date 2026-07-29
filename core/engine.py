#!/usr/bin/env python3
"""
通用评级引擎(全游戏共用)。

一方(side) = entities(实体列表)+ team(队伍名)。实体既可是"若干选手",也可是"队伍本身"。
队伍强度 = w · entity评级均值 + (1-w) · 队伍级评级。
  - w = 1.0 → 纯实体评级。若 entities=[队伍名],即"队伍级 Elo"(Dota2/CS2 用)。
  - w < 1.0 → 融合。entities=5 名选手 + 队伍名 → "选手+队伍协同"(LoL 用)。
换人自动按选手差值平移;side_adv 表示先手方(蓝方/radiant)先验;shrink 收缩概率修过度自信。
"""
from collections import defaultdict


def expect(diff, scale=400.0):
    return 1.0 / (1.0 + 10 ** (-diff / scale))


class _Elo:
    def __init__(self, K, Kp, prov, scale, base=1500.0, yr_reg=0.0):
        self.K, self.Kp, self.prov, self.scale, self.base, self.yr = K, Kp, prov, scale, base, yr_reg
        self.R = defaultdict(lambda: base)
        self.n = defaultdict(int)
        self.year = {}

    def mean(self, ids):
        return sum(self.R[i] for i in ids) / len(ids)

    def regress(self, ids, y):
        if not self.yr:
            return
        for i in ids:
            if self.year.get(i) not in (None, y):
                self.R[i] = self.base + self.yr * (self.R[i] - self.base)
            self.year[i] = y

    def update(self, aids, bids, a_won, side_adv):
        pe = expect(self.mean(aids) + side_adv - self.mean(bids), self.scale)
        s = 1.0 if a_won else 0.0
        for i in aids:
            k = self.Kp if self.n[i] < self.prov else self.K
            self.R[i] += k * (s - pe); self.n[i] += 1
        for i in bids:
            k = self.Kp if self.n[i] < self.prov else self.K
            self.R[i] += k * ((1 - s) - (1 - pe)); self.n[i] += 1


class RatingEngine:
    def __init__(self, w=1.0, scale=400, side_adv=0, shrink=1.0,
                 ent=(40, 60, 10), tm=(30, 50, 10), ent_yr=0.0, tm_yr=0.0):
        self.w, self.scale, self.side_adv, self.shrink = w, scale, side_adv, shrink
        self.ent = _Elo(*ent, scale=scale, yr_reg=ent_yr)
        self.tm = _Elo(*tm, scale=scale, yr_reg=tm_yr) if w < 1.0 else None

    def _strength(self, ents, team):
        e = self.ent.mean(ents)
        return e if self.tm is None else self.w * e + (1 - self.w) * self.tm.R[team]

    def regress(self, m, y):
        self.ent.regress(m["a"]["ents"] + m["b"]["ents"], y)
        if self.tm is not None:
            self.tm.regress([m["a"]["team"], m["b"]["team"]], y)

    def p_a(self, m, neutral=False):
        adv = 0 if neutral else self.side_adv
        raw = expect(self._strength(m["a"]["ents"], m["a"]["team"]) + adv
                     - self._strength(m["b"]["ents"], m["b"]["team"]), self.scale)
        return 0.5 + (raw - 0.5) * self.shrink

    def update(self, m):
        self.ent.update(m["a"]["ents"], m["b"]["ents"], m["a_won"], self.side_adv)
        if self.tm is not None:
            self.tm.update([m["a"]["team"]], [m["b"]["team"]], m["a_won"], self.side_adv)

    def team_strength(self, team, ents):
        return self._strength(ents, team)
