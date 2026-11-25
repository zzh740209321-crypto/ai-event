# 异动归因榜（以价格异动为起点反查新闻）

日界为 **UTC+8（Asia/Kuala_Lumpur）**。价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

窗口取跳变起点前 6h 至后 1h；晚于跳变的新闻标记为「事后解释/报道」并降低时间权。

## 2026-11-23 UTC+8 

生成时间：2026-11-25 08:57 UTC+8

### 共同因子

- **crypto_common**（2026-11-23 21:45 UTC+8，方向 UP）：DOGE/USDT +5.09%、ETH/USDT +2.72%、SOL/USDT +5.58%、XRP/USDT +4.69%、BNB/USDT +0.98%、ADA/USDT +5.72%、BTC/USDT +1.63%
  - 归因：未找到明确新闻，可能为流动性/清算/技术面（置信度 0.0，判定 NO_CLEAR_NEWS）
  - 候选：Solo bitcoin miner beats the odds to win $191,000 block reward（事前或同步，归因分 0.9586，单一权威（未交叉核实））
  - 候选：Can Jensen Huang Return to Nvidia?（事前或同步，归因分 0.8759，多源确认）
  - 候选：Trump-linked American Bitcoin secures $150M credit line from FalconX（事前或同步，归因分 0.8741，多源确认）
- **equity_common**（2026-11-23 22:30 UTC+8，方向 UP）：NVDA +31.32%、SPY +4.56%、QQQ +6.69%
  - 归因：英伟达董事会重新任命黄仁勋为总裁、首席执行官及董事会成员，此消息在盘前发布，并被视为利好，推动了股价上涨。（置信度 0.9755，判定 ATTRIBUTED）
  - 候选：NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director（事前或同步，归因分 0.9755，官方一手）
  - 候选：Can Jensen Huang Return to Nvidia?（事前或同步，归因分 0.9414，多源确认）
  - 候选：Nvidia soars as Jensen Huang returns to lead company（事前或同步，归因分 0.9297，多源确认）
- **cross_asset_spillover**（2026-11-23 22:30 UTC+8，方向 UP）：NVDA +31.32%、DOGE/USDT +5.09%、ETH/USDT +2.72%、SOL/USDT +5.58%、XRP/USDT +4.69%、BNB/USDT +0.98%、ADA/USDT +5.72%、BTC/USDT +1.63%、SPY +4.56%、QQQ +6.69%
  - 归因：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。（置信度 0.97，判定 ATTRIBUTED）
  - 候选：NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director（事前或同步，归因分 0.9755，官方一手）
  - 候选：Solo bitcoin miner beats the odds to win $191,000 block reward（事前或同步，归因分 0.9586，单一权威（未交叉核实））
  - 候选：Can Jensen Huang Return to Nvidia?（事前或同步，归因分 0.9414，多源确认）

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 核验 |
| --- | --- | --- | --- | --- | --- | --- |
| NVDA | +31.32% / +7.59 | 2026-11-23 22:30 UTC+8  窗口 +35.14% | 英伟达董事会重新任命黄仁勋为总裁、首席执行官及董事会成员，此消息在盘前发布，并被视为利好，推动了股价上涨。 | 0.98 | 事前或同步 | 官方一手 |
| DOGE/USDT | +5.09% / +1.66 | 2026-11-23 21:45 UTC+8  窗口 +6.47% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 多源确认 |
| ETH/USDT | +2.72% / +0.87 | 2026-11-23 21:45 UTC+8  窗口 +4.92% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 多源确认 |
| SOL/USDT | +5.58% / +1.84 | 2026-11-23 21:45 UTC+8  窗口 +5.50% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 多源确认 |
| XRP/USDT | +4.69% / +1.71 | 2026-11-23 21:45 UTC+8  窗口 +4.93% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 多源确认 |
| BNB/USDT | +0.98% / +0.37 | 2026-11-23 21:45 UTC+8  窗口 +3.83% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 多源确认 |
| ADA/USDT | +5.72% / +1.65 | 2026-11-23 21:45 UTC+8  窗口 +6.11% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 多源确认 |
| BTC/USDT | +1.63% / +0.72 | 2026-11-23 21:45 UTC+8  窗口 +4.15% | 未找到明确的标的直接新闻；交叉溢出：英伟达董事会重新任命黄仁勋为总裁、首席执行官和董事会成员，这可能提振了对科技股和更广泛市场（包括加密货币）的风险偏好。 | 0.97 | 事前或同步 | 单一权威（未交叉核实） |
| SPY | +4.56% / +2.79 | 2026-11-23 22:30 UTC+8  窗口 +3.79% | 英伟达董事会重新任命黄仁勋为总裁、首席执行官及董事会成员，此消息在盘前发布，并被视为利好，推动了股价上涨。 | 0.98 | 事前或同步 | 官方一手 |
| QQQ | +6.69% / +2.74 | 2026-11-23 22:30 UTC+8  窗口 +5.79% | 英伟达董事会重新任命黄仁勋为总裁、首席执行官及董事会成员，此消息在盘前发布，并被视为利好，推动了股价上涨。 | 0.98 | 事前或同步 | 官方一手 |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Can Jensen Huang Return to Nvidia? | TECH_AI | 124.458 | 多源确认 | 2026-11-23 21:19 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 2 | NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director | TECH_AI | 122.164 | 官方一手 | 2026-11-23 21:55 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 3 | Solo bitcoin miner beats the odds to win $191,000 block reward | CRYPTO | 84.667 | 单一权威（未交叉核实） | 2026-11-23 21:37 UTC+8 | BTC/USDT: 24h -3.90% | Ab24h +0.90% | 锚定 62895.36 | 仅展示，不参与排序 |
| 4 | Trump-linked American Bitcoin secures $150M credit line from FalconX | CRYPTO | 81.342 | 多源确认 | 2026-11-23 21:44 UTC+8 | BTC/USDT: 24h -3.90% | Ab24h +0.90% | 锚定 62895.36 | 仅展示，不参与排序 |
| 5 | Tech stocks see monster rally after Jensen Huang returns as Nvidia CEO | TECH_AI | 80.789 | 多源确认 | 2026-11-23 17:17 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 6 | Nvidia soars as Jensen Huang returns to lead company | POLITICS_REG | 77.302 | 多源确认 | 2026-11-23 22:13 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 7 | Bitcoin Rebounds to $61K After Weekend Plunge to Two-Year Low | CRYPTO | 36.829 | 多源确认 | 2026-11-23 19:14 UTC+8 | BTC/USDT: 24h -1.38% | Ab24h -0.35% | 锚定 61328.67 | 仅展示，不参与排序 |
| 8 | [Binance New Cryptocurrency Listing] Binance Will Launch Stock Options on Anthropic (ANT) | CRYPTO | 36.06 | 官方一手 | 2026-11-23 22:17 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 9 | Huang returns as Nvidia CEO after Trump intervention in abrupt board reversal | TECH_AI | 35.587 | 单一权威（未交叉核实） | 2026-11-23 21:59 UTC+8 | NVDA: 24h -10.31% | Ab24h -8.75% | 锚定 169.9899 | 仅展示，不参与排序 |
| 10 | Solo Bitcoin Miner Wins $190K Jackpot Against 130 Million-to-One Odds | CRYPTO | 34.616 | 单源未核实 | 2026-11-23 11:30 UTC+8 | BTC/USDT: 24h -1.41% | Ab24h +0.17% | 锚定 61240.01 | 仅展示，不参与排序 |

## 花费与局限

- LLM 模型：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
