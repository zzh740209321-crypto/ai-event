# 异动归因榜（以价格异动为起点反查新闻）

加密默认日界为 **UTC+8（Asia/Kuala_Lumpur）**；美股按 **美东（America/New_York，自动兼容 EST/EDT 夏令时）常规会话** 切日（含隔夜跳空），所有输出时间戳统一标注为 **UTC+8**。
价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

加密窗口取跳变起点前 6h 至后 1h；美股窗口取前 16h 至后 9h；晚于跳变的新闻均标记为「事后解释/报道」并降低时间权。

## 2026-11-24（market=us，输出时间 UTC+8）

生成时间：2026-11-25 09:28 UTC+8

### 会话行情切片（含非异动对照）

| 标的 | 开盘 (UTC+8) | 收盘 (UTC+8) | 隔夜跳空 | 会话涨跌 | z | 上一会话涨跌 / 回吐 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| NVDA | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -3.28% | -5.94% | -0.69 | +31.32%（回吐约 19.0%） |
| SMH | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -4.15% | -7.26% | -1.23 | +15.18%（回吐约 47.8%） |
| SOXX | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -4.60% | -8.29% | -1.33 | +13.66%（回吐约 60.6%） |
| QQQ | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -1.67% | -1.96% | -0.67 | +6.69%（回吐约 29.3%） |
| SPY | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -1.00% | -0.50% | -0.25 | +4.56% |
| DIA | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -0.43% | +0.82% | +0.50 | +3.00% |
| AAPL | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -0.45% | +1.25% | +0.68 | +2.05% |
| MSFT | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -0.51% | +0.64% | +0.26 | +1.64% |
| TSLA | 2026-11-24 22:30 UTC+8 | 2026-11-25 05:00 UTC+8 | -0.51% | -0.31% | -0.07 | +11.47% |

### 同会话宏观/利率（相对上日美股收盘）

- **DXY**（`DX-Y.NYB`）：104.344 → 103.826（-0.50%，盘中 +0.04%）
- **US10Y**（`^TNX`）：4.918 → 4.904（-0.28%，盘中 -0.08%）
- **US05Y**（`^FVX`）：4.728 → 4.712（-0.34%，盘中 -0.02%）

### 共同因子

- **equity_common**（2026-11-24 22:30 UTC+8，方向 DOWN）：SOXX -8.29%、SMH -7.26%、NVDA -5.94%、TSLA -0.31%
  - 归因：半导体板块（SOXX、SMH、NVDA）和科技股（QQQ）在隔夜大幅上涨后出现获利了结，尤其是英伟达（NVDA）的领导层/治理担忧新闻加剧了下跌。（置信度 0.92，判定 ATTRIBUTED）
  - 在线核查（`openrouter/perplexity/sonar`）：**confirmed** (VERIFIED) — 可确认 2026-11-24 当天，NVDA、SMH 以及半导体/AI相关资产整体回落，Reuters 明确报道 Nasdaq 期货和 AI 股因前一日 Nvidia 领涨后降温而下跌，且 NVDA 在盘中/开盘阶段走弱；SOXX 也被报道在盘前下跌约5%。关于“TSLA 同步下跌”的直接证据在已获取材料中不充分，因此该条对 TSLA 的归因仍偏弱，但整体“AI/芯片回吐、由 Nvidia 相关行情驱动”的主线得到确认。 [来源: https://247wallst.com/investing/2026/11/24/jensen-huang-could-still-be-kicked-out-nvidia-could-still-fall-40/, https://247wallst.com/investing/2026/11/24/the-u-s-just-blacklisted-the-firm-suspected-of-funneling-nvidia-chips-to-china/?.tsrc=rss, https://upside.pandobit.com/en/news/2026/11/jensen-huang-is-back-as-nvidia-ceo-but-investigations-and-risks-remain-2312296/]
  - 候选原因：**回吐前一日暴涨 / 获利了结**（事前或同步，归因分 0.9246，**confirmed**，独立源 6，权威 1.0）— Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally [Kitco](https://news.google.com/rss/articles/CBMisAFBVV95cUxPVmR3S0E4eC04el94LUNRcGJxUXo3MGppQ2Jxa19oQVIxVl9XNDJULV9BQ1R3cmZPZ1ZyckJXNmR0b3pwbW5NV0pLR0IwMTRabVJxQjN5QWlNRzVoQzU2T0RUYjNHWnpfS2VYSzJYeDhYNFQ2dVFMY3BRZHdrcEhQWE4tbHlRbHFxdVhVamRSelJIWnhDbklpcHJzUUY1UXN1a2s5Z0luUEREN1JfNlV3bA?oc=5) / [Seeking Alpha](https://news.google.com/rss/articles/CBMiqAFBVV95cUxQQVYwRms3V3E3Q0RiNmJTWFdvemZiV29hOXRzcUV3WmJTOUxLMXM4UDNvMFdoMXFmak5ZRmk2allfWmotT2lPMlMzLUxvSnRmcE1qRVltbFpCMGNuMmNwb0JLWXgzbXo5VXNSTFllNURudS1oZ0FlcE1TeG1pRWFqNUtLTnJJVkJoNzc3dVIzVmVSWms4eDJLOEsyNE5Vb21UNkFOYnBuRTA?oc=5)
  - 候选原因：**黄仁勋复职与董事会/治理风波**（事前或同步，归因分 0.854，**confirmed**，独立源 4，权威 1.0）— Jensen Huang Could Still Be Kicked Out, Nvidia Could Still Fall 40% [Yahoo Finance](https://news.google.com/rss/articles/CBMinAFBVV95cUxNZWdFbVNuLWc3TE12ekl6dmVhd3dnSEtLb1BlRTQ1WTFTemFzTTF5Tm5nQVQtcWVVZTBIajFQcGlFenF4Qi1zV09nRTdZOFhaSFh2UWZtRklzUzJrV1NrN3ZDT284R1dBYTc3andOVnUteHZEMXNZTldtcHU4a3lJdVhYTVJZMGdSX2V6TFRZb0tMMEVpcVQ2dEh2d24?oc=5) / [AP News](https://news.google.com/rss/articles/CBMipwFBVV95cUxQQUVQVndZcFVCS0N6M3plQS16cWctMi1ia2s3S0FqdDZoQzZwS3BZX3FZQUF3ZzZMMXdyLVd4WDM3cE9wMGMwd0RZSDJLekF4SUJaZ2VsQ1R3bXV1c0JhZWh6QnBkdERwNUo4VGQybHdGSkRSckZiTFAyMHM1aXlWYVI3TzF4OXR3WTYyZTJTaW9kaC1UTmZYbTRqa3djc2dGb19ZTG0xbw?oc=5)
  - 候选原因：**AI 资本开支回报与估值/个股情绪**（事前或同步，归因分 0.785，**single_source**，独立源 6，权威 0.76）— Drops for Nvidia, Anthropic and other AI stocks drag the US market back down [Yahoo Finance](https://news.google.com/rss/articles/CBMipAFBVV95cUxNdUVCY3pFVVBDUEwtWGlWa1ViLWE4eE9XeHk2R0s3MC1MSUpNblB6ZFZ5bmJPX0tXcGd2bk5FcVZHbW9oU3FNT2FwMzF4S05jNXlVRjBzZExNYWJ3ako5X24yVDhySHhnUU1HaGFxMUdjTGZsRHc0ZE1oREpqcjJoTHBORzdyWHRGXzhxbllTQ1pHc1hCdS1QVG9sSS1Gb3pkbkZVYw?oc=5) / [Tri City Record](https://news.google.com/rss/articles/CBMi6AFBVV95cUxOR2FlRzBRN1pxdldfcUFFcHFWMDBPMHhVRm5NOEVNTHNkckNWclRienhPRDcwb29WbW1RQlJBaGtiY1pwcjltMy1MbmVyQ2VBeXRTWEdDbVVCODI1eDZpYlF4YlJfT1NVMGVzaV83Ui1OMGlqYkpMaDFIVWpnOUctMER4SXM4bjROMWdFODcyejQ1MURNNkJwdWtOcnJzdUE2dGZYRndJc19QZURtZTlnVUx5d2RXZzlodzB4YjV2dlFGVHdxZTY4YllCcGQ2akJ5ZUFTMko4WWpscGVLa3A4Yjhvdk5NR0hT?oc=5)
  - 候选原因：**Rep. Jamie Raskin on Howard Lutnick probe: A profound confli**（事前或同步，归因分 0.7772，**single_source**，独立源 1，权威 0.88）— Rep. Jamie Raskin on Howard Lutnick probe: A profound conflict of interest [CNBC](https://news.google.com/rss/articles/CBMitgFBVV95cUxONE1MckpZTzJocmcyVTByY2dGcko2LUJCN01zNmMzcWNxRnh1ZE95YUZkZEtmd1duVF84U1hQRDJVLW8wZnhxRmNucWVNTnowNDRma3ZCUHN0TWkzQkdMQXpjNFowbFhkOTU4R0otRzhJZFY5MjJxQzlXWnIyV1drWnpTa1lPYXBORkxIUEMtWkhBNmZmWW1iSjAyVDU2TlNlcU5QazdoMGg5ZGRCYTROdU56ZUJFZw?oc=5)

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 自动核验 (tier / 独立源 / 权威) |
| --- | --- | --- | --- | --- | --- | --- |
| SOXX | -8.29% / -1.33 | 2026-11-24 22:30 UTC+8  窗口 -6.16% | 半导体板块（SOXX、SMH、NVDA）和科技股（QQQ）在隔夜大幅上涨后出现获利了结，尤其是英伟达（NVDA）的领导层/治理担忧新闻加剧了下跌。 | 0.92 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| SMH | -7.26% / -1.23 | 2026-11-24 22:30 UTC+8  窗口 -5.64% | 半导体板块（SOXX、SMH、NVDA）和科技股（QQQ）在隔夜大幅上涨后出现获利了结，尤其是英伟达（NVDA）的领导层/治理担忧新闻加剧了下跌。 | 0.92 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| AAPL | +1.25% / +0.68 | 2026-11-24 22:30 UTC+8  窗口 +0.77% | 苹果股价上涨，但科技股普遍下跌，特别是AI相关股票，这可能与对英伟达领导层和治理的担忧以及获利了结有关。 | 0.82 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=45, 1.0) |
| NVDA | -5.94% / -0.69 | 2026-11-24 22:30 UTC+8  窗口 -6.25% | 半导体板块（SOXX、SMH、NVDA）和科技股（QQQ）在隔夜大幅上涨后出现获利了结，尤其是英伟达（NVDA）的领导层/治理担忧新闻加剧了下跌。 | 0.92 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=30, 1.0) |
| TSLA | -0.31% / -0.07 | 2026-11-24 23:00 UTC+8  窗口 -2.72% | 半导体板块（SOXX、SMH、NVDA）和科技股（QQQ）在隔夜大幅上涨后出现获利了结，尤其是英伟达（NVDA）的领导层/治理担忧新闻加剧了下跌。 | 0.92 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=25, 1.0) |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | How important are Nvidia and Jensen Huang to the US economy? | TECH_AI | 163.061 | confirmed / 多源确认 | 2026-11-24 00:12 UTC+8 | NVDA: 暂无对齐行情 |
| 2 | Drops for Nvidia, Anthropic and other AI stocks drag the US market back down | TECH_AI | 144.262 | confirmed / 多源确认 | 2026-11-24 11:31 UTC+8 | NVDA: 暂无对齐行情 |
| 3 | Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally | TECH_AI | 108.693 | confirmed / 多源确认 | 2026-11-24 21:15 UTC+8 | NVDA: 暂无对齐行情 |
| 4 | 'Awaiting the king's return': Taiwan celebrates Huang's return to Nvidia | TECH_AI | 96.834 | confirmed / 多源确认 | 2026-11-24 15:29 UTC+8 | NVDA: 暂无对齐行情 |
| 5 | Jensen Huang Is Back at Nvidia. Here’s What to Know. | TRADFI | 89.59 | confirmed / 多源确认 | 2026-11-24 02:23 UTC+8 | NVDA: 24h -7.23% | Ab24h -6.54% | 锚定 165.165 | 仅展示，不参与排序 |
| 6 | Jensen Huang Could Still Be Kicked Out, Nvidia Could Still Fall 40% | TECH_AI | 89.088 | confirmed / 多源确认 | 2026-11-24 22:04 UTC+8 | NVDA: 暂无对齐行情 |
| 7 | Wall Street analysts scramble to upgrade Nvidia’s stock after Huang’s return | TECH_AI | 83.877 | confirmed / 多源确认 | 2026-11-24 02:11 UTC+8 | NVDA: 暂无对齐行情 |
| 8 | Why Nvidia Needed Jensen Huang Back—And What His Return Really Changes | TRADFI | 82.143 | confirmed / 多源确认 | 2026-11-24 03:57 UTC+8 | NVDA: 24h -5.88% | Ab24h -5.38% | 锚定 165.185 | 仅展示，不参与排序 |
| 9 | Nvidia shares fall more than 5% as Huang comeback rally cools | TECH_AI | 80.566 | confirmed / 多源确认 | 2026-11-24 17:12 UTC+8 | NVDA: 暂无对齐行情 |
| 10 | Stock Market News for Nov 24, 2026 | TECH_AI | 79.565 | confirmed / 多源确认 | 2026-11-24 16:08 UTC+8 | NVDA: 暂无对齐行情 |

## 花费与局限

- 归因 LLM：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
- 归因 LLM 调用 2 次（输入 3033 / 输出 152 tokens，约 $0.00036）；在线核查（`openrouter/perplexity/sonar`）调用 1 次（约 $0.00539），合计 **$0.00575**。
- 实时增量采集：909 条原始新闻 → 604 个簇。
