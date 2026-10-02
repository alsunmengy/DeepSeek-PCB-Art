#!/usr/bin/env python3
"""自绘 GitHub star history SVG：从仓库创建日到今天，主题色可配。
用法: python3 gen_chart.py <owner/repo> <color> <out.svg> [gh_token_env]
数据来源: gh api（需已登录）+ stargazers 接口（带 starred_at）
"""
import json, subprocess, sys, datetime, math, base64, os

W, H = 800, 420
M_L, M_R, M_T, M_B = 60, 30, 70, 46
PLOT_W, PLOT_H = W - M_L - M_R, H - M_T - M_B


def gh(args, raw=False):
    out = subprocess.run(["gh", "api"] + args, capture_output=True, text=True, check=True).stdout
    return out if raw else json.loads(out)


def fetch(repo):
    meta = gh(["repos/" + repo])
    created = datetime.datetime.fromisoformat(meta["created_at"].replace("Z", "+00:00"))
    stars = []
    page = 1
    while True:
        batch = gh(["repos/" + repo + "/stargazers?per_page=100&page=%d" % page,
                    "-H", "Accept: application/vnd.github.star+json"])
        if not batch:
            break
        stars += [datetime.datetime.fromisoformat(s["starred_at"].replace("Z", "+00:00")) for s in batch]
        if len(batch) < 100:
            break
        page += 1
    stars.sort()
    return meta, created, stars


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gen(repo, color, stars, created, meta):
    now = datetime.datetime.now(datetime.timezone.utc)
    total = len(stars)
    t0 = created
    t1 = now
    span = max((t1 - t0).total_seconds(), 1)

    def X(t):
        return M_L + (t - t0).total_seconds() / span * PLOT_W

    def Y(n):
        ymax = max(total, 1)
        # 刻度必须是整数：步长 = ceil(上限/4)，上限 = 步长*4
        step = max(1, math.ceil(ymax / 4))
        nice = step * 4
        return M_T + PLOT_H - n / nice * PLOT_H, nice

    _, ytop_nice = Y(total)

    # 阶梯路径：起点(创建日,0) → 每个 star 一次台阶 → 终点(今天,total)
    pts = [(M_L, M_T + PLOT_H)]
    n = 0
    for t in stars:
        n += 1
        pts.append((X(t), Y(n)[0]))
    pts.append((X(t1), Y(total)[0]))

    line = " ".join("%.1f,%.1f" % p for p in pts)
    area = line + " %.1f,%.1f %.1f,%.1f" % (X(t1), M_T + PLOT_H, M_L, M_T + PLOT_H)

    # 网格 + 刻度
    grid, ylabels = [], []
    for i in range(5):
        v = ytop_nice * i / 4
        y = M_T + PLOT_H - (v / ytop_nice) * PLOT_H
        grid.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#eaeaea" stroke-width="1"/>' % (M_L, y, W - M_R, y))
        ylabels.append('<text x="%.1f" y="%.1f" text-anchor="end" class="ax">%d</text>' % (M_L - 8, y + 4, v))

    xticks, xlabels = [], []
    days = span / 86400
    n_ticks = 5
    for i in range(n_ticks):
        t = t0 + datetime.timedelta(seconds=span * i / (n_ticks - 1))
        x = X(t)
        xticks.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#eaeaea" stroke-width="1"/>' % (x, M_T, x, M_T + PLOT_H))
        xlabels.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="ax">%s</text>' % (x, M_T + PLOT_H + 20, t.strftime("%m-%d") if days < 400 else t.strftime("%Y-%m")))

    end_x, end_y = X(t1), Y(total)[0]
    label_x = min(end_x - 6, W - M_R - 6)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">{esc(repo)} star history</title>
  <desc id="d">{total} GitHub stars from {t0.date()} to {t1.date()}</desc>
  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{color}" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="#ffffff"/>
  <style>
    .ttl{{font:700 17px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#1f2328}}
    .sub{{font:400 12.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;fill:#656d76}}
    .ax{{font:400 11.5px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill:#656d76}}
    .val{{font:700 13px -apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;fill="{color}"}}
  </style>
  <text x="{M_L}" y="30" class="ttl">★ {esc(repo)} · Star History</text>
  <text x="{M_L}" y="50" class="sub">{total} stars · {t0.date()} → {t1.date()}（创建至今）</text>
  {''.join(grid)}
  {''.join(xticks)}
  {''.join(ylabels)}
  {''.join(xlabels)}
  <polygon points="{area}" fill="url(#fill)"/>
  <polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" fill="{color}" stroke="#ffffff" stroke-width="2"/>
  <text x="{label_x:.1f}" y="{end_y - 12:.1f}" text-anchor="end" class="val">★ {total}</text>
  <text x="{M_L}" y="{H - 12}" class="ax">Source: GitHub stargazers API · auto-updated</text>
</svg>
'''


if __name__ == "__main__":
    repo, color, out = sys.argv[1], sys.argv[2], sys.argv[3]
    meta, created, stars = fetch(repo)
    svg = gen(repo, color, stars, created, meta)
    open(out, "w", encoding="utf-8").write(svg)
    print("%s -> %d stars, created %s, svg %d bytes" % (repo, len(stars), created.date(), len(svg.encode())))
