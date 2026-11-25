# 异动归因榜（以价格异动为起点反查新闻）

加密默认日界为 **UTC+8（Asia/Kuala_Lumpur）**；美股按 **美东（America/New_York，自动兼容 EST/EDT 夏令时）常规会话** 切日（含隔夜跳空），所有输出时间戳统一标注为 **UTC+8**。
价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

加密窗口取跳变起点前 6h 至后 1h；美股窗口取前 16h 至后 9h；晚于跳变的新闻均标记为「事后解释/报道」并降低时间权。

## 2026-11-23（market=us，输出时间 UTC+8）

生成时间：2026-11-25 09:29 UTC+8

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
  - 归因：英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。（置信度 0.98，判定 ATTRIBUTED）
  - 在线核查（`openrouter/perplexity/sonar`）：**confirmed** (VERIFIED) — 已确认：NVIDIA于2026-11-23宣布立即恢复Jensen Huang的President、CEO及董事身份，且SEC 8-K与公司新闻稿一致[1][2]。路透社同时报道特朗普介入并称该决定提振AI/半导体交易，但关于NVDA、TSLA、SMH、SPY、QQQ、SOXX、DIA、MSFT、AAPL整体在该日“全线上涨”的具体幅度与因果归因，当前只能确认相关性，不能严格证明所有标的都由这一单一驱动所致[1][3]. [来源: https://www.reuters.com/technology/nvidia-reinstates-jensen-huang-ceo-2026-11-23/, https://www.reuters.com/technology/trump-says-nvidia-board-made-right-call-huang-reinstatement-2026-11-23/, https://www.sec.gov/Archives/edgar/data/1045810/000104581026000090/nov23pressrelease.htm]
  - 候选原因：**黄仁勋复职与董事会/治理风波**（事前或同步，归因分 1.0389，**confirmed**，独立源 15，权威 1.0）— NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director [NVIDIA Newsroom](https://nvidianews.nvidia.com/news/nvidia-board-reinstates-jensen-huang-as-president-ceo-and-board-director) / [Reuters](https://news.google.com/rss/articles/CBMiiAFBVV95cUxOd19EYmc4X2wzaW5zXzZ5VXZ1cUFJbS1OYzJsZ2VSTVRnMkQteWdiN3Z0dTBlNmltdll6Vy1RWnpxVUthOF9XX3g0YmVvNWdXODJUMGpSeXdldVdYQWE3N2hCQXU3RExXSDViSWI3S2xHNVZFc0NUVmh5bGRhem5aUzdDa29xb1hH?oc=5)
  - 候选原因：**Trump rewrites the lame-duck rules with flex on Nvidia CEO**（事前或同步，归因分 0.8427，**confirmed**，独立源 2，权威 1.0）— Trump rewrites the lame-duck rules with flex on Nvidia CEO [Reuters](https://news.google.com/rss/articles/CBMiqgFBVV95cUxNc3l1T3NpNEY5eFRTQ0xVT2tBNjQyS3JFaUF3SmQydUpCY0RaZEFZWDgyaUdhTUR2R2xzamVmcTJjeHFzRDN2eVpEVjVneE5QWHc0ZXlrSWc3T0gwSFlUY1k4ZjYzbm1GbWVxWVdxYW1XU1daZWNCZkVGeUFRRkxZQnpJS1JpZHY1UGRYVTExM29fbTRmbkpOU3hWUVl6Y1BPUjQxZzlOQ2sxUQ?oc=5) / [Yahoo Finance](https://news.google.com/rss/articles/CBMikwFBVV95cUxOUE9uWXFoSnBSRWZ5THZSNy1LYmdNbnJ0eU5EVVN3emloLU9oNUVlWjBxMjMtLWg1TDB5RmNPVjNTd01ORkwwNzNWWnpQeGdYVXBGN0tZQ2xJNDNkT2hlc1pQaGZUeWc5am1OSTFkQ296VXZPOVFsY2dORTRhTHdlTURkV3AwODNUcHhIN3hKSm94T0E?oc=5)
  - 候选原因：**President Trump: I was represented at Nvidia's board meeting**（事后解释/报道，归因分 0.8029，**confirmed**，独立源 4，权威 1.0）— President Trump: I was represented at Nvidia's board meeting [CNBC](https://news.google.com/rss/articles/CBMiowFBVV95cUxOeW9SY0lBN1FfQlI5ZmZUMjVBb0xnT2hyMEtkalpUZ1N4QnNXalVDSzVzakJkOXN0Uk91UUljQlNpamgwWUx5Y3R3Qm5leEU3dDg4eXNvMjA2T1piVVp1MkdyZ1JlX3dsSUc5RmwtbUhOYnRBemlFNVA1SFZTNjRoYjVQQmNseXZpTXozaGxiUXhqQi1kbWRGVk9qTzFJbjJjLXow?oc=5) / [CNBC](https://news.google.com/rss/articles/CBMisAFBVV95cUxNV2xBWkJVS2xDZmJ5WUh5VXU5dzVOY0oyNDhHektYTy1xcDJoMFZWU2dOSmxMTmtYZUREc0stRzVhcXZxelRFb3FHODhlcjJyQ0dLUU9UcmQ4QjB2WXVYSnI5VHRQYTlGVG1Bc25ENnRHWS1waTF5RWlRN1RSYVI3V25RVlFMamhQdVY1NWxzMlNXc2tMNEZxSGxWeGpIOFd5NG10SHFtbkRmSDhXZFBTaA?oc=5)
  - 候选原因：**AI 资本开支回报与估值/个股情绪**（事前或同步，归因分 0.7948，**single_source**，独立源 4，权威 0.76）— Stock Market Today: Dow Jones, S&P 500, Nasdaq 100 Futures Rise After ANT IPO and Friday’s AI Rout— ORCL [Benzinga](https://news.google.com/rss/articles/CBMi7wFBVV95cUxOQkdKYWdvMkZIcGM5V3dMbjEwem4yRmhpVVZ6S2dPRnBLUzh3SFdUMmNEdW84NDZVZDJfV0NJU0Z3WmFLNWh5eC1Ba0dxb0tBcXhxN0ZkdTZwU19hNjdGX0t5Q3h6LVFIOTdEQnZHaGVnM19HMDRpQ3p6TDl1LXR0QWxpRHBxMmZJZjl0OHRwM09FNEJMS1J5aGhYdTZ1M2pXNzF4WE1ZZjZfZjZhbmd6ZWppdUQ2ZGtVYXlLNnVIdGNZZURIYWxwdUUwT1ltTHZPT21CZ1l2ZGtRcFlTeHJSc2tqOHhaUjAwMkhvMGRmOA?oc=5) / [Yahoo Finance](https://news.google.com/rss/articles/CBMikAFBVV95cUxQak1ESHkzdm5DLUU1SjRYR2xKQ0k3V3g0QmRmdlQ3Y2lKbDlRTk1ucWtfVHplQkotSDFfUW9zY0ZHYW5pTFlwSTBqNlp2UGxZdHBsNVdWbGo4dzNZRWhaNzdQeW9Ua3VLbW84ckNtTlZ2Ui0yNUpNT0FodllDQ0lMNEJERlAtM3l6V3hHdUlZQWM?oc=5)

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 自动核验 (tier / 独立源 / 权威) |
| --- | --- | --- | --- | --- | --- | --- |
| NVDA | +31.32% / +7.59 | 2026-11-23 22:30 UTC+8  窗口 +35.14% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| TSLA | +11.47% / +2.85 | 2026-11-23 22:30 UTC+8  窗口 +11.22% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| SMH | +15.18% / +3.25 | 2026-11-23 22:30 UTC+8  窗口 +15.15% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| SPY | +4.56% / +2.79 | 2026-11-23 22:30 UTC+8  窗口 +3.79% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| QQQ | +6.69% / +2.74 | 2026-11-23 22:30 UTC+8  窗口 +5.79% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| SOXX | +13.66% / +2.55 | 2026-11-23 22:30 UTC+8  窗口 +11.89% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| DIA | +3.00% / +2.06 | 2026-11-23 22:30 UTC+8  窗口 +2.22% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| MSFT | +1.64% / +0.67 | 2026-11-23 22:30 UTC+8  窗口 +3.50% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |
| AAPL | +2.05% / +1.14 | 2026-11-23 22:30 UTC+8  窗口 +1.26% | 英伟达股价大涨主要受黄仁勋复职担任CEO及董事会成员的消息驱动，此前有关于其领导层和公司治理的传闻，同时特朗普对黄仁勋的态度转变也对股价起到了积极影响。 | 0.98 | 含事前驱动 + 盘中/收盘跟进 | confirmed (n=29, 1.0) |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director | TECH_AI | 152.269 | confirmed / 官方一手 | 2026-11-23 21:55 UTC+8 | NVDA: 暂无对齐行情 |
| 2 | Jim Cramer: Jensen Huang’s return is 'so huge' for Nvidia and the AI trade | TECH_AI | 131.217 | confirmed / 多源确认 | 2026-11-23 23:53 UTC+8 | NVDA: 暂无对齐行情 |
| 3 | Wall Street soars on Huang's return to Nvidia, Treasury yields rise | TECH_AI | 126.412 | confirmed / 多源确认 | 2026-11-23 07:44 UTC+8 | NVDA: 暂无对齐行情 |
| 4 | Nvidia stock jumps as Trump makes U-turn on Jensen Huang | TECH_AI | 125.53 | confirmed / 多源确认 | 2026-11-23 19:34 UTC+8 | NVDA: 暂无对齐行情 |
| 5 | Can Jensen Huang Return to Nvidia? | TECH_AI | 124.458 | confirmed / 多源确认 | 2026-11-23 21:19 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 6 | Nvidia Brings Back Jensen Huang as Its CEO, 11 Days After He Resigned | TECH_AI | 110.038 | confirmed / 多源确认 | 2026-11-23 20:07 UTC+8 | NVDA: 暂无对齐行情 |
| 7 | President Trump: I was represented at Nvidia's board meeting | POLITICS_REG | 106.551 | confirmed / 多源确认 | 2026-11-23 23:37 UTC+8 | NVDA: 暂无对齐行情 |
| 8 | Stocks Soar as Huang’s Nvidia Return Fuels AI Bets: Markets Wrap | TECH_AI | 96.251 | confirmed / 多源确认 | 2026-11-23 06:02 UTC+8 | NVDA: 暂无对齐行情 |
| 9 | Solo bitcoin miner beats the odds to win $191,000 block reward | CRYPTO | 84.667 | single_source / 单一权威（未交叉核实） | 2026-11-23 21:37 UTC+8 | BTC/USDT: 24h -3.90% | Ab24h +0.90% | 锚定 62895.36 | 仅展示，不参与排序 |
| 10 | Trump-linked American Bitcoin secures $150M credit line from FalconX | CRYPTO | 81.342 | confirmed / 多源确认 | 2026-11-23 21:44 UTC+8 | BTC/USDT: 24h -3.90% | Ab24h +0.90% | 锚定 62895.36 | 仅展示，不参与排序 |

## 花费与局限

- 归因 LLM：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
- 归因 LLM 调用 1 次（输入 1388 / 输出 86 tokens，约 $0.00017）；在线核查（`openrouter/perplexity/sonar`）调用 1 次（约 $0.00542），合计 **$0.00559**。
- 实时增量采集：892 条原始新闻 → 469 个簇。
