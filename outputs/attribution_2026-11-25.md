# 异动归因榜（以价格异动为起点反查新闻）

日界为 **UTC+8（Asia/Kuala_Lumpur）**。价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

窗口取跳变起点前 6h 至后 1h；晚于跳变的新闻标记为「事后解释/报道」并降低时间权。

## 2026-11-25 UTC+8 （交易日未完结）

生成时间：2026-11-25 08:57 UTC+8

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 核验 |
| --- | --- | --- | --- | --- | --- | --- |
| BNB/USDT | +0.25% / +0.10 | 2026-11-25 01:00 UTC+8  窗口 +0.74% | 未找到明确新闻，可能为流动性/清算/技术面 | 0.10 | 无明显新闻 | — |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Huang Tells Staff He Is in Therapy, Apologizes in Nvidia Town Hall | TECH_AI | 79.024 | 多源确认 | 2026-11-25 04:09 UTC+8 | NVDA: 24h 窗口未结束（锚定 155.47，24h_window_pending） |
| 2 | Watch Bitcoin Sinks Below $60,000 Amid ETF Outflows | TRADFI | 61.025 | 单一权威（未交叉核实） | 2026-11-25 04:15 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59893.62，24h_window_pending） |
| 3 | Bitcoin miner CleanSpark swings to $987 million annual loss as BTC production declines | CRYPTO | 50.435 | 单一权威（未交叉核实） | 2026-11-25 06:10 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59832.0，24h_window_pending） |
| 4 | CleanSpark Returns to Q4 Profit on Bitcoin Gains, Revenue Falls 46% During AI Shift | TECH_AI | 48.381 | 多源确认 | 2026-11-25 05:53 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59986.01，24h_window_pending） |
| 5 | Nasdaq Resumes Selloff as Nvidia, Anthropic Shares Slump | TECH_AI | 46.686 | 单一权威（未交叉核实） | 2026-11-25 03:32 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59781.39，24h_window_pending） |
| 6 | Anthropic falls below its $83 IPO price on its fourth day of trading, faster than SpaceX | TRADFI | 46.532 | 单一权威（未交叉核实） | 2026-11-25 04:06 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59893.62，24h_window_pending） |
| 7 | Coldcard reveals how security reviews missed Bitcoin wallet flaw for over 5 years | CRYPTO | 37.648 | 单源未核实 | 2026-11-25 03:04 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59781.39，24h_window_pending） |
| 8 | Coldcard Bitcoin Exploit, Revisited: How a Hidden Flaw Survived Years of Audits | CRYPTO | 34.923 | 单源未核实 | 2026-11-25 05:16 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 59986.01，24h_window_pending） |
| 9 | Exclusive / SEC Is Probing Nvidia Amid Departure of CEO Jensen Huang | TECH_AI | 34.471 | 单一权威（未交叉核实） | 2026-11-25 07:49 UTC+8 | NVDA: 暂无对齐行情 |
| 10 | 'AI trade never died': Traders see room for market recovery, but bitcoin's participation is another story | CRYPTO | 33.864 | 单一权威（未交叉核实） | 2026-11-25 00:00 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 60108.01，24h_window_pending） |

## 花费与局限

- LLM 模型：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
