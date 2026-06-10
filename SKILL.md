---
name: worldcup-daily
version: "1.0.0"
description: "生成世界杯日报——自动采集 Google News RSS、懂球帝、直播吧、Reddit、YouTube、Polymarket 等信源，输出结构化的日报 markdown，支持金山文档自动发布。"
argument-hint: 'worldcup-daily 生成最新日报 | worldcup-daily 2026-06-15'
allowed-tools: Bash, WebSearch, WebFetch
author: 湾湾
---

# 世界杯日报 Skill

每天自动生成世界杯日报，采集多源数据，格式化输出。

## 使用方式

生成最新日报：
```bash
python3 scripts/run.py
```

指定日期：
```bash
python3 scripts/run.py --date 2026-06-15
```

## 信源

| 层级 | 信源 | 采集方式 |
|------|------|----------|
| 脚本采集 | Google News RSS | curl + XML 解析 |
| 脚本采集 | 懂球帝 | curl + SSR 解析 |
| 脚本采集 | 直播吧 | curl + 正则提取 |
| last30days | Reddit + YouTube + Polymarket | last30days CLI |
| 兜底 | site: 搜索 | WebSearch |

## 配置

需要配置的文件：
- `~/.config/worldcup_daily/.env` — ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL
- `~/.config/last30days/.env` — last30days 配置

金山文档发布需要：
- `kdocs-cli` 已安装并认证
- `KDOCS_FILE_ID` 设置为目标文档 ID

## 输出

- 本地：`~/Desktop/未命名文件夹/世界杯日报/{date}.md`
- 金山：每天 prepend 到指定文档
