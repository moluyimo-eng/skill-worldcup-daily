# 世界杯日报 Skill

每天自动生成世界杯日报，采集多源数据，输出结构化 markdown。

## 信源

- Google News RSS（外媒头条）
- 懂球帝（中文体育 SSR）
- 直播吧足球频道（48h 过滤）
- last30days（Reddit + YouTube + Polymarket）
- WebSearch site: 兜底

## 安装

1. 安装依赖：
```bash
pip install anthropic
brew install claude-code  # or npm install -g @anthropic-ai/claude-code
```

2. 安装 last30days skill：
```bash
# 从 ClawHub 安装 last30days
claude install last30days
```

3. 安装 kdocs-cli（可选，用于金山文档发布）：
```bash
curl -fsSL https://wpsai.wpscdn.cn/skillhub/pro/v2.5.8/setup.sh | bash
kdocs-cli auth set-token <your-token>
```

4. 配置环境变量：
```bash
mkdir -p ~/.config/worldcup_daily
cat > ~/.config/worldcup_daily/.env << EOF
ANTHROPIC_AUTH_TOKEN=your_token
ANTHROPIC_BASE_URL=https://api.anthropic.com
EOF
```

5. 验证：
```bash
python3 scripts/run.py
```

## 定时任务

```bash
# macOS launchd：每天 9:00 自动运行
cp com.zhihu.worldcup-daily.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zhihu.worldcup-daily.plist
```
