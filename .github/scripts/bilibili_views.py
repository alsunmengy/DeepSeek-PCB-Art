#!/usr/bin/env python3
"""采集 B 站单个视频的播放量，写入 .github/view-history/history.json。

用法:
  python3 bilibili_views.py             # 只打印当前播放量
  python3 bilibili_views.py --snapshot  # 采集并写入/更新「今天」的快照
  python3 bilibili_views.py --bootstrap # 首次建立回推估算段（history 里还没有 backfill 时）

环境变量:
  BVID           默认 BV1vbet6dEA8
  BILI_SESSDATA  可选，登录态 cookie；只有匿名 buvid3 被风控挡死时才需要

为什么这么绕（GitHub Actions 是 Azure 机房 + 海外出口）:
  * 裸请求 x/web-interface/view 大概率 412 / code -352；
  * 先取 x/frontend/finger/spi 的 buvid3/buvid4 带上 Cookie，能过绝大多数风控；
  * 仍失败就退避重试（实测风控窗口约 20 秒），再不行解析视频页 __INITIAL_STATE__ 兜底。
"""
import datetime
import gzip
import json
import math
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import zlib

BVID = os.environ.get("BVID", "BV1vbet6dEA8").strip()
HIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "view-history", "history.json")
API = "https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
PAGE = "https://www.bilibili.com/video/{bvid}/"
FINGER = "https://api.bilibili.com/x/frontend/finger/spi"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def _decode(resp):
    raw = resp.read()
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        raw = gzip.decompress(raw)
    elif "deflate" in enc:
        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw.decode("utf-8", "replace")


def get(url, cookie="", timeout=20.0):
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", UA)
    req.add_header("Referer", "https://www.bilibili.com/")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, _decode(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, _decode(e)
        except Exception:
            return e.code, ""


def bootstrap_cookie():
    try:
        status, body = get(FINGER)
        if status == 200:
            d = json.loads(body).get("data") or {}
            b3, b4 = d.get("b_3"), d.get("b_4")
            if b3:
                return "buvid3=%s" % b3 + (("; buvid4=%s" % b4) if b4 else "")
    except Exception as exc:
        print("[warn] buvid 预热失败: %s" % exc, file=sys.stderr)
    return ""


def fetch_once(bvid, cookie):
    status, body = get(API.format(bvid=bvid), cookie)
    if status == 200:
        try:
            p = json.loads(body)
        except json.JSONDecodeError:
            p = None
        if p and p.get("code") == 0:
            d = p["data"]
            return {
                "view": int(d["stat"]["view"]),
                "title": d.get("title") or "",
                "pubdate": datetime.datetime.fromtimestamp(
                    d["pubdate"], datetime.timezone(datetime.timedelta(hours=8))
                ).isoformat(),
                "url": "https://www.bilibili.com/video/%s/" % d.get("bvid", bvid),
            }
        if p:
            print("[info] view API code=%s msg=%s" % (p.get("code"), p.get("message")), file=sys.stderr)
    else:
        print("[info] view API HTTP %s: %s" % (status, body[:160]), file=sys.stderr)

    # 兜底：页面里的 __INITIAL_STATE__ 有同一个 stat 对象
    status, html = get(PAGE.format(bvid=bvid), cookie, timeout=30.0)
    if status == 200:
        m = re.search(r'"stat":\{"aid":\d+,"view":(\d+)', html)
        if m:
            t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
            print("[info] 走页面兜底", file=sys.stderr)
            return {
                "view": int(m.group(1)),
                "title": (t.group(1).strip() if t else ""),
                "pubdate": None,
                "url": "https://www.bilibili.com/video/%s/" % bvid,
            }
    return None


def fetch(bvid):
    cookie = bootstrap_cookie()
    sess = (os.environ.get("BILI_SESSDATA") or "").strip()
    if sess:
        cookie = (cookie + "; SESSDATA=" + sess) if cookie else "SESSDATA=" + sess
    delays = [0, 8, 15, 25, 40]
    for i, d in enumerate(delays, 1):
        if d:
            time.sleep(d)
        print("[info] 第 %d/%d 次尝试" % (i, len(delays)), file=sys.stderr)
        got = fetch_once(bvid, cookie)
        if got:
            return got
        if i == 2 and not cookie:
            cookie = bootstrap_cookie() or cookie
    return None


def load():
    if os.path.exists(HIST):
        try:
            return json.load(open(HIST, encoding="utf-8"))
        except Exception:
            pass
    return {"schemaVersion": 1, "bvid": BVID, "backfill": [], "snapshots": []}


def save(h):
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(h, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def make_backfill(pub_date, anchor_date, anchor_view):
    """发布日 → 昨天的每日累计播放量（双指数回推，单调递增，锚定当日实测值）。

    形状：0.55*(1-e^(-d/2.5)) + 0.45*(1-e^(-d/25))，d 为发布后天数。
    即前几天吃推荐位（快），之后是长尾（慢）。
    """
    def shape(d):
        return 0.55 * (1 - math.exp(-d / 2.5)) + 0.45 * (1 - math.exp(-d / 25.0))

    span = (anchor_date - pub_date).days
    if span < 1:
        return []
    scale = anchor_view / shape(span)
    out = [{"date": pub_date.isoformat(), "view": 0}]
    for d in range(1, span):
        out.append({"date": (pub_date + datetime.timedelta(days=d)).isoformat(),
                    "view": int(round(scale * shape(d)))})
    return out


def main():
    args = sys.argv[1:]
    snap = "--snapshot" in args
    boot = "--bootstrap" in args

    got = fetch(BVID)
    if not got:
        print("[error] 取不到播放量（大概率被风控）；本次不改动 history.json", file=sys.stderr)
        return 1

    h = load()
    h.setdefault("schemaVersion", 1)
    h["bvid"] = BVID
    h["title"] = got["title"] or h.get("title", "")
    h["url"] = got["url"]
    if got.get("pubdate"):
        h["pubdate"] = got["pubdate"]

    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    if boot and not h.get("backfill"):
        pubd = None
        if h.get("pubdate"):
            try:
                pubd = datetime.datetime.fromisoformat(h["pubdate"]).date()
            except Exception:
                pubd = None
        if pubd and pubd < today:
            h["backfill"] = make_backfill(pubd, today, got["view"])
            h["backfillMethod"] = ("双指数回推 0.55*(1-e^(-d/2.5))+0.45*(1-e^(-d/25))，"
                                   "锚定 %s 的实测 %d" % (today.isoformat(), got["view"]))
            h["backfilledAt"] = now.isoformat().replace("+00:00", "Z")
            print("[info] 生成回推段 %d 天" % len(h["backfill"]), file=sys.stderr)

    if snap:
        snaps = [s for s in h.get("snapshots", []) if s.get("date") != today.isoformat()]
        snaps.append({"t": now.isoformat().replace("+00:00", "Z"),
                      "date": today.isoformat(),
                      "view": got["view"]})
        snaps.sort(key=lambda s: s.get("t", ""))
        h["snapshots"] = snaps
        save(h)
        print("[info] 快照 %s = %d（共 %d 个）" % (today.isoformat(), got["view"], len(snaps)),
              file=sys.stderr)

    if not snap and not boot:
        print(json.dumps(got, ensure_ascii=False))
    else:
        print("view=%d" % got["view"])
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write("view=%d\n" % got["view"])
        summ = os.environ.get("GITHUB_STEP_SUMMARY")
        if summ:
            with open(summ, "a", encoding="utf-8") as f:
                f.write("- B站播放量 **%s** · %s\n" % (format(got["view"], ","), got["title"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
