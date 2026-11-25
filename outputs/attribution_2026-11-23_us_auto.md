# 异动归因榜（以价格异动为起点反查新闻）

加密默认日界为 **UTC+8（Asia/Kuala_Lumpur）**；美股按 **美东（America/New_York，自动兼容 EST/EDT 夏令时）常规会话** 切日（含隔夜跳空），所有输出时间戳统一标注为 **UTC+8**。
价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

加密窗口取跳变起点前 6h 至后 1h；美股窗口取前 16h 至后 9h；晚于跳变的新闻均标记为「事后解释/报道」并降低时间权。

## 2026-11-23（market=us，输出时间 UTC+8）

生成时间：2026-11-25 09:38 UTC+8

### 会话行情切片（含非异动对照）

| 标的 | 开盘 (UTC+8) | 收盘 (UTC+8) | 隔夜跳空 | 会话涨跌 | z | 上一会话涨跌 / 回吐 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| NVDA | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +32.79% | +31.32% | +7.59 | -13.84% |
| SMH | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +17.48% | +15.18% | +3.25 | -10.73% |
| SOXX | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +15.24% | +13.66% | +2.55 | -10.60% |
| QQQ | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +7.53% | +6.69% | +2.74 | -5.43% |
| SPY | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +4.84% | +4.56% | +2.79 | -3.48% |
| DIA | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +2.69% | +3.00% | +2.06 | -1.94% |
| AAPL | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +1.49% | +2.05% | +1.14 | -1.84% |
| MSFT | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +4.34% | +1.64% | +0.67 | -2.64% |
| TSLA | 2026-11-23 22:30 UTC+8 | 2026-11-24 04:30 UTC+8 | +8.29% | +11.47% | +2.85 | -7.55% |

### 同会话宏观/利率（相对上日美股收盘）

- **DXY**（`DX-Y.NYB`）：103.859 → 104.344（+0.47%，盘中 +0.14%）
- **US10Y**（`^TNX`）：4.912 → 4.918（+0.12%，盘中 -0.61%）
- **US05Y**（`^FVX`）：4.701 → 4.728（+0.57%，盘中 -0.78%）

### 共同因子

- **equity_common**（2026-11-23 22:30 UTC+8，方向 UP）：NVDA +31.32%、TSLA +11.47%、SMH +15.18%、SPY +4.56%、QQQ +6.69%、SOXX +13.66%、DIA +3.00%、MSFT +1.64%、AAPL +2.05%
  - 归因：英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。（置信度 0.95，判定 ATTRIBUTED）
  - 在线核查（`openrouter/perplexity/sonar`）：**unverified** (ERROR) —  
  - 候选原因：**黄仁勋复职与董事会/治理风波**（事前或同步，归因分 1.0318，**confirmed**，独立源 15，权威 1.0）— NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director [NVIDIA Newsroom](https://nvidianews.nvidia.com/news/nvidia-board-reinstates-jensen-huang-as-president-ceo-and-board-director) / [CBS News](https://news.google.com/rss/articles/CBMickFVX3lxTFBEZ2IzdVdRZFN3QXJ4djZjWVZBcEtKWURLaGhwaG4xNzUyV3dXMXJtdktYUlNMaHo2eWtEdHNIeUhXLVpZaEV1dVRvd1pPaGpNelY4aERWQ1NZblk5cVdzOHpZbVFhRk9IcUlMamI5MnNLZw?oc=5)
  - 候选原因：**Stock Market Today: Dow, S&P 500, and Nasdaq Surge as Nvidia**（事前或同步，归因分 0.8183，**unverified**，独立源 2，权威 0.55）— Stock Market Today: Dow, S&P 500, and Nasdaq Surge as Nvidia Leads a Major AI Rebound [24/7 Wall St.](https://news.google.com/rss/articles/CBMiwwFBVV95cUxOQ3RqNWFVcFdnMkhKYUp6NWlwR2MzQTZfSG9xb0NKZlhHY2xGVFFpOS1SS2Q0WVM1U0swSkluQmtEakZFRmdwYkV0RnR2VjVpMktWR0MxY1ZxRFY3akhicGRINUdkVzl6Vm5YOU80bW51d3owc0VQazMzX3dNekRWekV6VFJWMGR0RjVSY1hEenhsVXNtZEVfU0V5YXZaaktka1IyenpFbTBabXZqRGtmaWpXbXFmU1VQbGtKYUx0enlXbjQ?oc=5) / [Coinpaper](https://news.google.com/rss/articles/CBMimgFBVV95cUxOczRlU2MySEY5bkZvWG4xTDJBVXpsQnlhcGZ1MTZvTWZRV3dtNWM3X0dhYzN4ZGk0a2lVMzJZbk5GMk1DUzdnaG1xVmJ4TWl2RklOYklWZE5Uc01NakdkczNRam9sVVFYcVh5aU8xTWlOUm1sVVFyLTFuX01MLXVmZGtWcmd3bGxfaGlaU1IzN1VWdFphaEJoNmt3?oc=5)
  - 候选原因：**NVDA SEC Form 4 Filing**（事前或同步，归因分 0.7809，**confirmed**，独立源 1，权威 1.0）— NVDA SEC Form 4 Filing [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000090/nvda-20261122.htm) / [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1045810/000169684126000016/xslF345X06/wk-form4_1795470863.xml)
  - 候选原因：**AI 资本开支回报与估值/个股情绪**（事前或同步，归因分 0.7694，**unverified**，独立源 3，权威 0.55）— Stock Market Today: Dow Jones, S&P 500, Nasdaq 100 Futures Rise After ANT IPO and Friday’s AI Rout— ORCL [Benzinga](https://news.google.com/rss/articles/CBMi7wFBVV95cUxOQkdKYWdvMkZIcGM5V3dMbjEwem4yRmhpVVZ6S2dPRnBLUzh3SFdUMmNEdW84NDZVZDJfV0NJU0Z3WmFLNWh5eC1Ba0dxb0tBcXhxN0ZkdTZwU19hNjdGX0t5Q3h6LVFIOTdEQnZHaGVnM19HMDRpQ3p6TDl1LXR0QWxpRHBxMmZJZjl0OHRwM09FNEJMS1J5aGhYdTZ1M2pXNzF4WE1ZZjZfZjZhbmd6ZWppdUQ2ZGtVYXlLNnVIdGNZZURIYWxwdUUwT1ltTHZPT21CZ1l2ZGtRcFlTeHJSc2tqOHhaUjAwMkhvMGRmOA?oc=5) / [TradingView](https://news.google.com/rss/articles/CBMijwJBVV95cUxQS3dqVGdkQThqOEJyU25NdFNJb0xmaHVLSnotanRMc3ktZkV2TkdJbnlsZEVxc2ZUdzNxM1VKeDQtMDlQaFYxSDd5UHZsTFd3OFhSUnZabERuRUtBQm94WWJDYS1Gd20xcEg0MHFDMUZVN2FGSGpYREJvYkJHMTk2OW1LcWR6ZkxjZi1ZUWNITl9MMlA1Yl9BRzh6TzhnMzJ3b1hqLWVhcThBMlhiNUxteTJWei1UTE5YczVuSFlNTjRmTmFKVmFfekVUQWhNS09oT1F6SDFSbDlXb0ItcFljaEYyZDlDYll2Vm4zdDR4eXNnMVl6TkJDQ2FzQ2dMUG5ZTnpoWklxbWQyck4wUzQ0?oc=5)
  - 候选原因：**美联储利率 / PCE / 通胀预期**（事前或同步，归因分 0.763，**single_source**，独立源 2，权威 1.0）— COMMENTARY: AI bubble burst could put Fed rate cuts on the table [Reuters](https://news.google.com/rss/articles/CBMitAFBVV95cUxOeUxld0JxUDNGX2hDTXg0REFBSFoyWWRXbWcwdUtLMTJmOEJMbl94TG1zSHIwN2hKUUxOWWVFUy12dnlYNGpCVnBoejVLbTRZY1RrdjVCT2UyczA5WkUwUnRJQWZHOHU0ZjFHT1JBWHJSbGZkNmJEaWN5ODViNW5JYm02ekhBNDlXRzB2TG1yWVRHWGdma3F3SmRXU1BVWVVRZ3JDNTVfOThnWnVGdzMzdzA1bXI?oc=5) / [TradingView](https://news.google.com/rss/articles/CBMi-AFBVV95cUxOTUdTYXZNUzl6WS1oYmRSWHpHRDBUbHBwdGF6Ym84QjZfd0xHVXNTNHdqUUNaVEpUblBHRUJQcFRRVGRjOEQyd1h4OS1oN1pXSzRzNDA4RzJEXzNSaDFZcHMtTlNFeUJObXo5d3o4M3AzXzNrQ0xGWFJBd3hRazE1LXBTOFF3eHhQQ3Q4X0x3eGhmbk4wQ0VCS3M4aEpHVzlyUEJDTTNPNkFOX0hkcVRzVnNPY3d2bXktRjl0bVBoU21meV9TVWJ6YUsxZ04xWDRjSkZEU1lxY3RSQmU2YktoU3BxdkhuT01iMDF3MW9IWEw0ZENKeFc3LQ?oc=5)

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 自动核验 (tier / 独立源 / 权威) |
| --- | --- | --- | --- | --- | --- | --- |
| NVDA | +31.32% / +7.59 | 2026-11-23 22:30 UTC+8  窗口 +35.14% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| TSLA | +11.47% / +2.85 | 2026-11-23 22:30 UTC+8  窗口 +11.22% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| SMH | +15.18% / +3.25 | 2026-11-23 22:30 UTC+8  窗口 +15.15% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| SPY | +4.56% / +2.79 | 2026-11-23 22:30 UTC+8  窗口 +3.79% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| QQQ | +6.69% / +2.74 | 2026-11-23 22:30 UTC+8  窗口 +5.79% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| SOXX | +13.66% / +2.55 | 2026-11-23 22:30 UTC+8  窗口 +11.89% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| DIA | +3.00% / +2.06 | 2026-11-23 22:30 UTC+8  窗口 +2.22% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| MSFT | +1.64% / +0.67 | 2026-11-23 22:30 UTC+8  窗口 +3.50% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |
| AAPL | +2.05% / +1.14 | 2026-11-23 22:30 UTC+8  窗口 +1.26% | 英伟达股价大涨31.32%，主要受黄仁勋复职担任CEO及董事会治理风波消息的推动，同时AI板块整体反弹也提振了市场情绪，尽管宏观利率环境略有收紧。 | 0.95 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=28, 1.0) |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director | TECH_AI | 148.094 | confirmed / 官方一手 | 2026-11-23 21:55 UTC+8 | NVDA: 暂无对齐行情 |
| 2 | Jim Cramer: Jensen Huang’s return is 'so huge' for Nvidia and the AI trade | TECH_AI | 127.583 | confirmed / 多源确认 | 2026-11-23 23:53 UTC+8 | NVDA: 暂无对齐行情 |
| 3 | Can Jensen Huang Return to Nvidia? | TECH_AI | 124.458 | confirmed / 多源确认 | 2026-11-23 21:19 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 4 | Wall Street soars on Huang's return to Nvidia, Treasury yields rise | TECH_AI | 121.77 | confirmed / 多源确认 | 2026-11-23 07:44 UTC+8 | NVDA: 暂无对齐行情 |
| 5 | Nvidia stock jumps as Trump makes U-turn on Jensen Huang | TECH_AI | 114.363 | confirmed / 多源确认 | 2026-11-23 19:34 UTC+8 | NVDA: 暂无对齐行情 |
| 6 | Nvidia Brings Back Jensen Huang as Its CEO, 11 Days After He Resigned | TECH_AI | 110.038 | confirmed / 多源确认 | 2026-11-23 20:07 UTC+8 | NVDA: 暂无对齐行情 |
| 7 | Stocks Soar as Huang’s Nvidia Return Fuels AI Bets: Markets Wrap | TECH_AI | 96.251 | confirmed / 多源确认 | 2026-11-23 06:02 UTC+8 | NVDA: 暂无对齐行情 |
| 8 | President Trump: I was represented at Nvidia's board meeting | POLITICS_REG | 86.6 | confirmed / 多源确认 | 2026-11-23 23:37 UTC+8 | NVDA: 暂无对齐行情 |
| 9 | Solo bitcoin miner beats the odds to win $191,000 block reward | CRYPTO | 84.667 | single_source / 单一权威（未交叉核实） | 2026-11-23 21:37 UTC+8 | BTC/USDT: 24h -3.90% | Ab24h +0.90% | 锚定 62895.36 | 仅展示，不参与排序 |
| 10 | AAPL Nov 2026 310.000 call (AAPL261123C00310000) stock price, news, quote and history | TECH_AI | 83.015 | confirmed / 多源确认 | 2026-11-23 23:30 UTC+8 | NVDA: 暂无对齐行情 |

## 花费与局限

- 归因 LLM：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
- 归因 LLM 调用 1 次（输入 1745 / 输出 87 tokens，约 $0.00021）；在线核查（`openrouter/perplexity/sonar`）调用 1 次（约 $0.00000），合计 **$0.00021**。
- 实时增量采集：907 条原始新闻 → 516 个簇。
- 在线核查状态：ERROR（402 Client Error: Payment Required for url: https://openrouter.ai/api/v1/chat/completions）。本地多源/官方核验结论不受影响。
