#!/usr/bin/env python3
"""世界杯日报自动生成 v2 — 信源硬控，Claude 只做 site: 搜索 + 排版。
每天 9:00 由 launchd 触发。"""

import subprocess, sys, os, re, json, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPORT_DIR = Path.home() / "Desktop/未命名文件夹/世界杯日报"
LOG_FILE = Path.home() / "scripts/worldcup_daily.log"
CLAUDE_BIN = "/opt/homebrew/bin/claude"
KDOCS_BIN = Path.home() / ".local/bin/kdocs-cli"
LAST30DAYS = Path.home() / ".claude/skills/last30days/scripts/last30days.py"
KDOCS_FILE_ID = "mah5JAjGc1M8uCaMGXF3rxusQNSBhLxF1"  # 世界杯日报云文档
CST = timezone(timedelta(hours=8))
ENV_FILE = Path.home() / ".config/worldcup_daily/.env"
CURL_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ── helpers ───────────────────────────────────────────────────────

def _log(msg: str) -> None:
    """同时输出到 stdout 和日志文件。"""
    timestamp = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _parse_rss_date(raw: str) -> str:
    """'Tue, 09 Jun 2026 03:15:39 GMT' → '06.09' (CST)"""
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw).astimezone(CST)
        return dt.strftime("%m.%d")
    except Exception:
        return ""


# ── Layer 1: 信源采集 ────────────────────────────────────────────

def fetch_google_news_rss() -> str:
    """抓取 Google News World Cup RSS，返回格式化的文本块。"""
    _log("[采集] Google News RSS ...")
    url = "https://news.google.com/rss/search?q=world+cup+2026+fifa&hl=en-US&ceid=US:en"
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20,
        )
        root = ET.fromstring(result.stdout)
        lines = []
        count = 0
        for item in root.findall(".//item"):
            title = (item.find("title").text or "").strip() if item.find("title") is not None else ""
            link = (item.find("link").text or "").strip() if item.find("link") is not None else ""
            pubdate = (item.find("pubDate").text or "").strip() if item.find("pubDate") is not None else ""
            source = (item.find("source").text or "").strip() if item.find("source") is not None else ""
            date_cn = _parse_rss_date(pubdate)
            if not title:
                continue
            lines.append(f"- **{title}** ({source}{' · ' + date_cn if date_cn else ''})\n  {link}")
            count += 1
        _log(f"[采集] Google News: {count} 条")
        return "\n".join(lines) if lines else "(Google News RSS 暂无数据)"
    except Exception as e:
        _log(f"[采集] Google News 失败: {e}")
        return f"(Google News RSS 采集失败: {e})"


def collect_last30days() -> str:
    """调用 last30days CLI，采集 Reddit + Polymarket + YouTube。"""
    _log("[采集] last30days (Reddit + Polymarket + YouTube) ...")
    try:
        result = subprocess.run(
            [sys.executable, str(LAST30DAYS),
             "2026 World Cup football soccer",
             "--search", "reddit,polymarket,youtube",
             "--days", "2", "--emit", "md", "--quick"],
            capture_output=True, text=True, timeout=180,
            env={**os.environ, "LAST30DAYS_MEMORY_DIR": str(
                Path.home() / ".config/last30days/memory")},
        )
        if result.returncode != 0:
            _log(f"[采集] last30days 错误: {result.stderr[:200]}")
            return f"(last30days 采集失败: {result.stderr[:200]})"
        # 去掉 warning 噪音和尾部 agent 报告
        lines = result.stdout.splitlines()
        start = 0
        end = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("# last30days") or line.startswith("🌐"):
                start = i
                break
        for i in range(len(lines) - 1, start, -1):
            if lines[i].startswith("✅") or lines[i].startswith("🔴") or lines[i].startswith("---"):
                end = i
            else:
                break
        output = "\n".join(lines[start:end]) if start else result.stdout
        _log(f"[采集] last30days: {len(output)} 字符")
        return output
    except subprocess.TimeoutExpired:
        _log("[采集] last30days 超时")
        return "(last30days 采集超时)"
    except Exception as e:
        _log(f"[采集] last30days 失败: {e}")
        return f"(last30days 采集失败: {e})"


def fetch_dongqiudi() -> str:
    """抓取懂球帝首页 SSR 内容，提取世界杯相关标题。"""
    _log("[采集] 懂球帝 ...")
    url = "https://www.dongqiudi.com/"
    wc_kw = ['世界杯', '世体', '阿斯', '队报', 'TA', '贝林', '姆巴佩', '梅西',
             'C罗', '内马尔', '阿根廷', '巴西', '法国', '德国', '西班牙', '英格兰',
             '开幕', '揭幕', 'FIFA', '美加墨', '裁判', '门票', '球衣']
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", "15", url,
             "-H", f"User-Agent: {CURL_UA}"],
            capture_output=True, text=True, timeout=20,
        )
        titles = re.findall(
            r'class="(?:headline__title|news-card__title)[^"]*"[^>]*>([^<]+)',
            result.stdout,
        )
        lines = []
        for t in titles:
            t = t.strip()
            if any(kw in t for kw in wc_kw):
                lines.append(f"- {t} (懂球帝)")
                if len(lines) >= 30:
                    break
        _log(f"[采集] 懂球帝: {len(lines)} 条")
        return "\n".join(lines) if lines else "(懂球帝今日暂无世界杯相关内容)"
    except Exception as e:
        _log(f"[采集] 懂球帝 失败: {e}")
        return f"(懂球帝采集失败: {e})"


def fetch_zhibo8() -> str:
    """抓取直播吧足球频道，提取世界杯相关标题和链接。"""
    _log("[采集] 直播吧 ...")
    url = "https://news.zhibo8.com/zuqiu/"
    wc_kw = ['世界杯', '美加墨', 'FIFA', '阿根廷', '巴西', '法国', '德国',
             '西班牙', '英格兰', '葡萄牙', '中国裁判', '马宁', '开幕', '揭幕',
             '世预赛', '巡礼', '球场', '热身赛', '参赛', '名单', '荷兰']
    # 只保留最近48小时的新闻
    today = datetime.now(CST)
    valid_dates = {today.strftime("%Y-%m-%d"),
                   (today - timedelta(days=1)).strftime("%Y-%m-%d")}
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", "15", url,
             "-H", f"User-Agent: {CURL_UA}"],
            capture_output=True, text=True, timeout=20,
        )
        items = re.findall(
            r'<a[^>]*href="(//news\.zhibo8\.com/[^"]*/(\d{4}-\d{2}-\d{2})/[^"]*)"[^>]*>([^<]{10,})</a>',
            result.stdout,
        )
        seen = set()
        lines = []
        for href, date_str, title in items:
            if date_str not in valid_dates:
                continue
            title = title.strip()
            if title in seen:
                continue
            if any(kw in title for kw in wc_kw):
                seen.add(title)
                date_cn = date_str[-5:].replace("-", ".")
                lines.append(f"- {title} (直播吧 · {date_cn})\n  https:{href}")
                if len(lines) >= 40:
                    break
        _log(f"[采集] 直播吧: {len(lines)} 条 (48h过滤后)")
        return "\n".join(lines) if lines else "(直播吧今日暂无世界杯相关内容)"
    except Exception as e:
        _log(f"[采集] 直播吧 失败: {e}")
        return f"(直播吧采集失败: {e})"


# ── Layer 2: Prompt 构建 ─────────────────────────────────────────

def make_prompt(date_str: str, gnews_data: str, l30d_data: str,
                dongqiudi_data: str, zhibo8_data: str) -> str:
    now = datetime.now(CST)
    today_cn = now.strftime("%Y年%m月%d日")
    yesterday_cn = (now - timedelta(days=1)).strftime("%Y年%m月%d日")
    weekday_cn = ["一","二","三","四","五","六","日"][now.weekday()]
    days_left = (datetime(2026, 6, 11).date() - now.date()).days

    return f"""今天是{today_cn}（周{weekday_cn}），距2026世界杯开幕还有{days_left}天。
时间范围：绝对只包含 {yesterday_cn} 和 {today_cn} 两天的内容。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 已采集数据（⚠️ 必须优先使用，这是记者团队为你准备的素材）

以下四个来源独立采集，互不重叠。每个板块必须明确标注数据出处（域名+日期）。

### A. 外媒（Google News RSS）★ 优先级最高
覆盖 ESPN/BBC/CBS/The Athletic/FOX Sports/Guardian/Sky 等主流媒体。

{gnews_data}

### B. 中文体育 · 懂球帝
抓取自懂球帝首页。

{dongqiudi_data}

### C. 中文体育 · 直播吧
抓取自直播吧足球频道（48h内）。

{zhibo8_data}

### D. Reddit / YouTube / Polymarket（last30days）
社交平台和预测市场数据。

{l30d_data}

### ⚠️ 素材使用规则（必须遵守）

每个板块的素材来源分配：
- **今日头条**：A（外媒）主导，B/C 补充。不能纯中文源。
- **各队动态**：A 占至少 40%，B/C 合计不超过 60%。每个队标来源域名。
- **创意/视觉**：A/B/C 任意组合，D 的 YouTube 如有也可用。
- **话题/争议**：A 占至少一半。
- **场外文化**：A/B/C 任意。
- **数据/预测**：A 主导，D(Polymarket) 补充。
- **中国视角**：B/C 主导，不能用 A。
- **UGC话题**：由头引用日报中的事件，话题覆盖A场外文化/B情绪认同/C技术社会讨论三类。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 补充搜索（site: 兜底，素材不够时用）

- site:dongqiudi.com 世界杯 2026
- site:zhibo8.com 世界杯
- site:espn.com world cup 2026
- site:fifa.com world cup 2026
- site:skysports.com world cup 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 🚫 黑名单

什么值得买 / 新浪科技 / 新浪财经 / 网易自媒体 / 百家号 / 搜狐号 / 搜狐 / 知乎专栏 /
中华网 / jpchinapress / stnn.cc / shangbaoindonesia / bolavip / 凤凰网 / 新华报业网 /
中国科技网 / 新唐人。以上来源即使出现在搜索结果中也必须删除。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 输出格式（严格遵守，# 层级不改）

# 世界杯日报 · {today_cn}（周{weekday_cn}）
距开幕还有 {days_left} 天

## 1. 今日头条
[1-2件当天最重要的事，各3-4句，主要来自外媒 RSS]

## 2. 各队动态
| 球队 | 动态 | 亮点 | 潜力 | 来源 |
|------|------|------|:--:|------|
| 🇧🇷 巴西 | ... | ... | ⭐ | 域名 · 日期 |
[至少8行。必须混用 A/B/C 三个来源，不能全是一个源]

## 3. 创意/视觉
[球衣/meme/社媒创意。至少2条]

## 4. 话题/争议
[门票/FIFA/裁判/球迷。至少3条]

## 5. 场外文化
[穿搭/联名/二创。至少2条]

## 6. 数据/预测
[赔率/预测。至少1条。优先用 D(last30days/Polymarket)+A(RSS)]

## 7. 中国视角
[⚠️ 至少2条。优先用 B(懂球帝) 和 C(直播吧) 素材。不够再用 site: 搜索补充。每条标注域名+日期。无法获取时写「今日暂无」，严禁用 AIGC 营销文填充。]

## 8. 今日 UGC 互动话题
[⚠️ 严格按以下规范生成，至少6条。每条引用日报中的具体事件作为"由头"，但话题本身必须是用户能直接参与的轻量互动。]

话题规范：
- 句式：名词短语/偏正结构/动宾结构，4-12字。禁用"如何""为什么""怎样""吗"。
- 视角：第一人称（我的XXX）或群体标签（早八人、考据党、显眼包、打工人、佛系球迷等）。
- 内核：具象场景+情绪锚点，落脚在微小场景或特定情绪。不要抽象分析。
- 门槛：用户看了30秒内就能决定发什么，最好能拍照/截图/晒图参与。
- 格式：序号. 话题文案 → 由头（引用日报中的事件）| 参与门槛描述

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 输出规则

- **第一个字符就是 `#`**，严禁前言后语
- 每条动态末尾标注来源域名和日期（如 `ESPN · 06.08`、`懂球帝 · 06.09`）
- 禁止的元描述：搜索过程、工具状态、数据来源方式、"今日暂无"的原因解释
- 黑名单来源 → 删除。日期不符（早于 {yesterday_cn}）→ 删除。"""


# ── Layer 3: 调用 Claude ─────────────────────────────────────────

def run(date_str: str) -> str | None:
    cfg = _load_env(ENV_FILE)
    env = os.environ.copy()
    env.update({
        "ANTHROPIC_AUTH_TOKEN": cfg.get("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_BASE_URL": cfg.get("ANTHROPIC_BASE_URL", ""),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": cfg.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", ""),
    })

    # Step 1: 采集原始数据（全在脚本层，不依赖 Claude 工具）
    gnews_data = fetch_google_news_rss()
    l30d_data = collect_last30days()
    dongqiudi_data = fetch_dongqiudi()
    zhibo8_data = fetch_zhibo8()

    # Step 2: 构建 prompt
    prompt = make_prompt(date_str, gnews_data, l30d_data, dongqiudi_data, zhibo8_data)

    # Step 3: 调用 Claude（site: 搜索作为兜底）
    _log(f"[日报] 生成 {date_str} ...")
    result = subprocess.run(
        [CLAUDE_BIN, "-p", prompt, "--output-format", "text",
         "--allowedTools", "WebSearch,WebFetch"],
        capture_output=True, text=True, timeout=600, env=env,
    )
    if result.returncode != 0:
        _log(f"[日报] Claude 错误: {result.stderr}")
        return None

    content = result.stdout
    path = REPORT_DIR / f"{date_str}.md"
    path.write_text(content)
    _log(f"[日报] 本地保存到 {path}")

    # Step 4: 追加到金山文档
    _kdocs_append(content)

    return str(path)


def _kdocs_append(content: str) -> None:
    """追加日报内容到金山云文档。"""
    payload_path = Path("/tmp/kdocs_append.json")
    payload_path.write_text(json.dumps({
        "file_id": KDOCS_FILE_ID,
        "content": content,
        "format": "markdown",
        "mode": "prepend",
    }, ensure_ascii=False))
    try:
        result = subprocess.run(
            [str(KDOCS_BIN), "otl", "insert-content", "--file", str(payload_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and '"code": 0' in result.stdout:
            _log("[金山] 追加成功")
        else:
            _log(f"[金山] 追加失败: {result.stderr or result.stdout[:200]}")
    except Exception as e:
        _log(f"[金山] 追加异常: {e}")


# ── entry ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.now(CST).strftime("%Y-%m-%d")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = run(today)
    sys.exit(0 if p else 1)
