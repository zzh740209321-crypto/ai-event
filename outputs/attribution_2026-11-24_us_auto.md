# 异动归因榜（以价格异动为起点反查新闻）

加密默认日界为 **UTC+8（Asia/Kuala_Lumpur）**；美股按 **美东（America/New_York，自动兼容 EST/EDT 夏令时）常规会话** 切日（含隔夜跳空），所有输出时间戳统一标注为 **UTC+8**。
价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

加密窗口取跳变起点前 6h 至后 1h；美股窗口取前 16h 至后 9h；晚于跳变的新闻均标记为「事后解释/报道」并降低时间权。

## 2026-11-24（market=us，输出时间 UTC+8）

生成时间：2026-11-25 09:38 UTC+8

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
  - 归因：英伟达（Nvidia）领涨的AI板块在经历前一日的暴涨后出现获利了结和回吐，导致纳斯达克期货下跌，拖累了包括SOXX和SMH在内的半导体股票，尽管宏观环境（如美元走弱和利率下降）和部分地缘政治（如关税预期）因素也可能有所影响，但AI板块的估值回调是主要驱动力。（置信度 0.95，判定 ATTRIBUTED）
  - 在线核查（`openrouter/perplexity/sonar`）：**confirmed** (VERIFIED) — 可核实的驱动是：11月24日美股期货因AI/芯片股降温而下跌，Reuters明确写到“Nvidia-fueled rally”后AI相关股票失去动能，且NVDA盘前下跌；同时特朗普政府已于11月23日将与Nvidia相关的Megaspeed列入贸易黑名单，这一消息也被Reuters和Semafor确认。 [来源: https://www.reuters.com/business/us-blacklist-megaspeed-chip-firm-linked-nvidia-scandal-source-says-2026-11-23/, http://rmb.reuters.com/rmd/rss/item/tag:reuters.com,2026:newsml_KCN3WY2B1?channel=frL012, https://www.reuters.com/world/singapore-investigating-nvidia-linked-megaspeed-after-us-blacklisting-2026-11-24/]
  - 候选原因：**回吐前一日暴涨 / 获利了结**（事前或同步，归因分 0.9246，**confirmed**，独立源 6，权威 1.0）— Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally [Kitco](https://news.google.com/rss/articles/CBMisAFBVV95cUxPVmR3S0E4eC04el94LUNRcGJxUXo3MGppQ2Jxa19oQVIxVl9XNDJULV9BQ1R3cmZPZ1ZyckJXNmR0b3pwbW5NV0pLR0IwMTRabVJxQjN5QWlNRzVoQzU2T0RUYjNHWnpfS2VYSzJYeDhYNFQ2dVFMY3BRZHdrcEhQWE4tbHlRbHFxdVhVamRSelJIWnhDbklpcHJzUUY1UXN1a2s5Z0luUEREN1JfNlV3bA?oc=5) / [Seeking Alpha](https://news.google.com/rss/articles/CBMiqAFBVV95cUxQQVYwRms3V3E3Q0RiNmJTWFdvemZiV29hOXRzcUV3WmJTOUxLMXM4UDNvMFdoMXFmak5ZRmk2allfWmotT2lPMlMzLUxvSnRmcE1qRVltbFpCMGNuMmNwb0JLWXgzbXo5VXNSTFllNURudS1oZ0FlcE1TeG1pRWFqNUtLTnJJVkJoNzc3dVIzVmVSWms4eDJLOEsyNE5Vb21UNkFOYnBuRTA?oc=5)
  - 候选原因：**AI 资本开支回报与估值/个股情绪**（含事前驱动 + 盘中/收盘跟进，归因分 0.7965，**single_source**，独立源 7，权威 0.88）— Briefs: Nvidia, Anthropic and other AI stocks get back to tumbling and drag the U.S. market lower [Tri City Record](https://news.google.com/rss/articles/CBMi6AFBVV95cUxOR2FlRzBRN1pxdldfcUFFcHFWMDBPMHhVRm5NOEVNTHNkckNWclRienhPRDcwb29WbW1RQlJBaGtiY1pwcjltMy1MbmVyQ2VBeXRTWEdDbVVCODI1eDZpYlF4YlJfT1NVMGVzaV83Ui1OMGlqYkpMaDFIVWpnOUctMER4SXM4bjROMWdFODcyejQ1MURNNkJwdWtOcnJzdUE2dGZYRndJc19QZURtZTlnVUx5d2RXZzlodzB4YjV2dlFGVHdxZTY4YllCcGQ2akJ5ZUFTMko4WWpscGVLa3A4Yjhvdk5NR0hT?oc=5) / [Daily Camera](https://news.google.com/rss/articles/CBMieEFVX3lxTE42UlViYklwUEJ5OWJRQ013REZETmxhVlowRlJGYWtpdXJUV3RPY1k3R2p6SnhHdmdveW03Qk5UM3BOTkw1eVlaMUhVa0VJVkx2RGxBemdtTzVHdEl1b3RRdUZkQ1JMQi10R3BhS2ZpbnNHZ0tMUkh2Tw?oc=5)
  - 候选原因：**Wall Street's sugar high quickly disappears as Nvidia and ot**（事前或同步，归因分 0.7882，**unverified**，独立源 3，权威 0.55）— Wall Street's sugar high quickly disappears as Nvidia and other AI stocks tumble again [Yakima Herald-Republic](https://news.google.com/rss/articles/CBMioAJBVV95cUxNd2w5SGxhRFFtcU5FOHNVbFMwaG5INm9peWVLeHd1UFlpcWZHbW1QczJxYjkxNnVoZFMyVUppVFYyZmcyV211MzB0d2lzeFQxM3ZMbFJsSGp3UGItUzhfRUlSbkRab05IWEZrdjZvTGt4d0E2YnJWa3BNSy1QbDVxdktNajN6N0VoMElRaThpVE9xQTRPV21IWnZ1bzZTclBaekduMzVhY0JyVlpCWG9COE1MRmg5ZDBGU0dlOElWQ1VhUzU0VzhnZFJIUUhiZ1hkT0sxeFh5dzhLQUk4aWNrMGhZWmd3SzRXZUZLQ0hDeWhSd1JMNmQzR09uTnFrREVZUHcxWlFBWGh1VE1ZZXRTTXE4Vk0xZkM5WTlpTXlCSDDSAaYCQVVfeXFMTzhWenhWR3FBV2g4MEJ1YU4zSTZjZldhRFc0TnFROWlrMXVTMzNkVGU2Q0lVR0htYUVlNHNuWkpqSUZrSEsybEktUzJoVzJwOXZVS3ByZXRkM2hTOFlBZ2VrQ291eFRNM1dQVDJtQTNFX2dnY0RURm84TnFhd3EzZ2R6Q2t6SG9yTHdCWEtoYnJyaXUzSXlkRWMxaF9VaTBaUkdtYmZqcHFWLURWWmsyOVMzT2JPMi1hRGJOdmtLTUhyZlhCMklyLXVZa1dhLWl4alF2Z2t4cXd3YlhlOGJkME9ISmJQOXdTOVdzTXY5eldHYnUxUVJ6cmw3bFQ2c1NwWFpVemwzbWkxb2RWQUxOUDJRNEpHaVBJcGo3RHU3U19qeGxoTEJR?oc=5) / [Union-Bulletin](https://news.google.com/rss/articles/CBMiiAJBVV95cUxNY0dyN3BBT1BOM3JDMHUzS1o2WWlsOXh6WFJBa256elB2Nk1pWjByVzFrN0FHRk5VTWo2a3VUX29qdkFxYmZSR0F2RWRJYXpfaEpmN0JMUjNZOFpUcjZpOEZ0XzBMcUFMMGxQSmlpaHpSNEUwOWFLRE9ycmpOdVlFWVpNN1RXXzlyaW9xT1lkQnZJV1ozSUZhUE1SdVl6MXJvczJkOGRta2lMWEplcW9zM25tZE0xa2JEUWdLcU1CSV9Tc3gyWENYeFhvUkJvZkdhb3JaV0VQRk9hYUJINmRNODAtczZUZXNBZ21IREU0TktrdUFpeVlKM3ZxV2NqU3l0LVZ0Y19kTFg?oc=5)
  - 候选原因：**Trump Administration Imposes Sanctions on Megaspeed, Singapo**（事前或同步，归因分 0.7645，**single_source**，独立源 1，权威 0.89）— Trump Administration Imposes Sanctions on Megaspeed, Singaporean Firm at Center of Nvidia Scandal [NYT Business](https://www.nytimes.com/2026/11/23/business/trump-administration-megaspeed-trade-blacklist-nvidia.html)
  - 候选原因：**关税与贸易摩擦预期**（事前或同步，归因分 0.7529，**single_source**，独立源 4，权威 0.76）— US prepares new tariffs on China, EU and other trading partners – WSJ [FXStreet](https://news.google.com/rss/articles/CBMiqgFBVV95cUxQWW02Mzc3ZzZDb0c1LXNLQlVQbi1JUVVQU0Q3UHRma2NlMHFzNzFJZ1lteUM4dGxDeTNNUkJ4dXdxcUlUX3FOQmxzT053OTRfaGtCODFSbVRfbW81TjUycEpSZUhvYThiX0ZrLXBmdTFzZ3Z6OVdFeXFGMnBCT21ob3lrOUNCdWt3SjdhZHN5ck1MSW1sdkI2ZkJEZDl2dDFUdzhyTl9iTU5RQQ?oc=5) / [BBC Business](https://www.bbc.co.uk/news/articles/c893r9ke5p97o?at_medium=RSS&at_campaign=rss)
  - 候选原因：**Sen. Kevin Cramer on Nvidia fallout: National security remai**（事前或同步，归因分 0.7406，**single_source**，独立源 1，权威 0.88）— Sen. Kevin Cramer on Nvidia fallout: National security remains the top priority for me [CNBC](https://news.google.com/rss/articles/CBMixgFBVV95cUxNb05NLXdjUDBPWS00ZXNKWHhib3Y0Z0hLbURtal94Y18zZGZBTHBsR24xTF9tRlJwa3Z2UEZoUkxQek5NYV9iS3hVa0YzUTVjNEVHVmprWGVnY1FMbjB2MldaSW4xcTFVWG54aGt6RkNVbDZINThkRWlZYjNzTjFKTGFWVDR2MjM1N1pSd0E2YkVRZ2U3ZGFNekplaUFGUzlxQ0ZHajJlTEl2WHY5SG13Y0NibXplWGVhRU5XdFBHRkwwNFZHLXc?oc=5)
  - 候选原因：**Bitcoin Falls as NVIDIA Selloff Hits Miners with AI Exposure**（事前或同步，归因分 0.7334，**unverified**，独立源 1，权威 0.55）— Bitcoin Falls as NVIDIA Selloff Hits Miners with AI Exposure [Analytics Insight](https://news.google.com/rss/articles/CBMinwFBVV95cUxNN2ZzRjJPaTBYdWRraUJfQTZlNGNKNkRNMkozbnREbDRqQWc1Ty1nSlFSRUVFME5OVkhlZEdTaWZMWG9tYU1LR0gzazEybVhHR1MxRUoxd1FLMG5OVmtqbVJUaEx1YmpsNTRRUXliWGRiTGE1aHU0Q0FwLWw5bUVkNXY5dFB0U2ZLZGRyUl90emhESTRaMF9BRThMMkdmM03SAawBQVVfeXFMTW05dWRrRjMza25MaWg3T3FfODdpZThGTFYzQ09IN0dXRXdCQ0MxSmMtbnVfVmdQcTdnNlZ2dUpFVnZqYVhxb2s1Ny1HQ3ZyT0xFSDdfVzFxZEpTY0FRTFluVTc5dkMwNDZhV25QRWQxMWJwYVMyUGhzMWNRb1RrWC05MXQ0YTRGNl9ib1RIM0xYMEE2SlhfZ2pZbWliUm1RR19xQ2tJTGhfVkZZbA?oc=5)

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 自动核验 (tier / 独立源 / 权威) |
| --- | --- | --- | --- | --- | --- | --- |
| SOXX | -8.29% / -1.33 | 2026-11-24 22:30 UTC+8  窗口 -6.16% | 英伟达（Nvidia）领涨的AI板块在经历前一日的暴涨后出现获利了结和回吐，导致纳斯达克期货下跌，拖累了包括SOXX和SMH在内的半导体股票，尽管宏观环境（如美元走弱和利率下降）和部分地缘政治（如关税预期）因素也可能有所影响，但AI板块的估值回调是主要驱动力。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| SMH | -7.26% / -1.23 | 2026-11-24 22:30 UTC+8  窗口 -5.64% | 英伟达（Nvidia）领涨的AI板块在经历前一日的暴涨后出现获利了结和回吐，导致纳斯达克期货下跌，拖累了包括SOXX和SMH在内的半导体股票，尽管宏观环境（如美元走弱和利率下降）和部分地缘政治（如关税预期）因素也可能有所影响，但AI板块的估值回调是主要驱动力。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| AAPL | +1.25% / +0.68 | 2026-11-24 22:30 UTC+8  窗口 +0.77% | 当日逆势于SOXX、SMH、NVDA、TSLA的DOWN行情，未找到该标的自身明确且方向一致的新闻，可能为板块轮动/个股分流。 | 0.45 | 逆势于DOWN | CONTRARIAN / 未套用板块叙事 |
| NVDA | -5.94% / -0.69 | 2026-11-24 22:30 UTC+8  窗口 -6.25% | 英伟达（Nvidia）领涨的AI板块在经历前一日的暴涨后出现获利了结和回吐，导致纳斯达克期货下跌，拖累了包括SOXX和SMH在内的半导体股票，尽管宏观环境（如美元走弱和利率下降）和部分地缘政治（如关税预期）因素也可能有所影响，但AI板块的估值回调是主要驱动力。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| TSLA | -0.31% / -0.07 | 2026-11-24 23:00 UTC+8  窗口 -2.72% | 英伟达（Nvidia）领涨的AI板块在经历前一日的暴涨后出现获利了结和回吐，导致纳斯达克期货下跌，拖累了包括SOXX和SMH在内的半导体股票，尽管宏观环境（如美元走弱和利率下降）和部分地缘政治（如关税预期）因素也可能有所影响，但AI板块的估值回调是主要驱动力。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=25, 1.0) |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | How important are Nvidia and Jensen Huang to the US economy? | TECH_AI | 164.306 | confirmed / 多源确认 | 2026-11-24 00:12 UTC+8 | NVDA: 暂无对齐行情 |
| 2 | Jensen Huang Is Back at Nvidia, but Bettors Are Already Wagering on His Exit and Divorce | TECH_AI | 119.104 | confirmed / 多源确认 | 2026-11-24 17:43 UTC+8 | NVDA: 暂无对齐行情 |
| 3 | Wall Street analysts scramble to upgrade Nvidia’s stock after Huang’s return | TECH_AI | 110.296 | confirmed / 多源确认 | 2026-11-24 02:11 UTC+8 | NVDA: 暂无对齐行情 |
| 4 | Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally | TECH_AI | 108.693 | confirmed / 多源确认 | 2026-11-24 21:15 UTC+8 | NVDA: 暂无对齐行情 |
| 5 | 'Awaiting the king's return': Taiwan celebrates Huang's return to Nvidia | TECH_AI | 105.598 | confirmed / 多源确认 | 2026-11-24 15:29 UTC+8 | NVDA: 暂无对齐行情 |
| 6 | Jensen Huang Is Back at Nvidia. Here’s What to Know. | TRADFI | 89.59 | confirmed / 多源确认 | 2026-11-24 02:23 UTC+8 | NVDA: 24h -7.23% | Ab24h -6.54% | 锚定 165.165 | 仅展示，不参与排序 |
| 7 | Jensen Huang and the Cult of the Male Tech Founder | TECH_AI | 89.247 | confirmed / 多源确认 | 2026-11-24 23:47 UTC+8 | NVDA: 暂无对齐行情 |
| 8 | TSLA Nov 2026 255.000 call (TSLA261123C00255000) stock price, news, quote and history | TECH_AI | 88.534 | confirmed / 多源确认 | 2026-11-24 09:54 UTC+8 | NVDA: 暂无对齐行情 |
| 9 | Why Nvidia Needed Jensen Huang Back—And What His Return Really Changes | TRADFI | 82.143 | confirmed / 多源确认 | 2026-11-24 03:57 UTC+8 | NVDA: 24h -5.88% | Ab24h -5.38% | 锚定 165.185 | 仅展示，不参与排序 |
| 10 | Nvidia's longtime CFO and now former interim CEO Colette Kress was left in the dark about Jensen Huang's return: Report | TECH_AI | 79.922 | confirmed / 多源确认 | 2026-11-24 17:59 UTC+8 | NVDA: 暂无对齐行情 |

## 花费与局限

- 归因 LLM：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
- 归因 LLM 调用 1 次（输入 1935 / 输出 128 tokens，约 $0.00024）；在线核查（`openrouter/perplexity/sonar`）调用 1 次（约 $0.00537），合计 **$0.00562**。
- 实时增量采集：958 条原始新闻 → 608 个簇。
