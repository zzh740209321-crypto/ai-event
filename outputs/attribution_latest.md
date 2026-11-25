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

## 2026-11-24 UTC+8 

生成时间：2026-11-25 08:57 UTC+8

### 共同因子

- **crypto_common**（2026-11-24 23:00 UTC+8，方向 DOWN）：SOL/USDT -7.41%、ADA/USDT -6.45%、DOGE/USDT -5.93%
  - 归因：比特币ETF出现5.7亿美元净流出，导致比特币跌破6万美元，并可能引发了加密货币市场的普遍下跌。（置信度 0.72，判定 ATTRIBUTED）
  - 候选：Bitcoin’s Hash Rate Drops 8% as Miners Switch Off Equipment（事前或同步，归因分 0.7602，单源未核实）
  - 候选：South Korea proposes ending 2017 ICO ban to boost jobs and onshore crypto investment（事前或同步，归因分 0.7565，单一权威（未交叉核实））
  - 候选：Bitcoin ETFs see another $570 million in net outflows as November total nears $5 billion and BTC dips below $60K（事前或同步，归因分 0.7227，单一权威（未交叉核实））
- **crypto_common**（2026-11-24 00:00 UTC+8，方向 DOWN）：XRP/USDT -6.44%、ETH/USDT -5.74%
  - 归因：未找到明确新闻，可能为流动性/清算/技术面（置信度 0.0，判定 NO_CLEAR_NEWS）
  - 候选：How market depth shapes the price of a weekend Bitcoin sale（事前或同步，归因分 0.6676，单源未核实）
  - 候选：Merry Making: Play, Build and Create With NVIDIA Technologies This Holiday Season（事前或同步，归因分 0.7451，官方一手）
  - 候选：Tom Lee Says Ethereum Is as Scarce as Bitcoin—And Bitmine Just Bought More（事前或同步，归因分 0.7313，多源确认）
- **crypto_common**（2026-11-24 10:00 UTC+8，方向 DOWN）：BTC/USDT -4.55%、BNB/USDT -3.75%
  - 归因：美股下跌，因英伟达（Nvidia）的上涨势头消退，美元下跌。（置信度 0.77，判定 ATTRIBUTED）
  - 候选：Dollar climbs as renewed AI euphoria fuels Fed rate hike bets（事前或同步，归因分 0.7747，单源未核实）
  - 候选：US stocks slide as Nvidia rally fizzles out, dollar falls（事前或同步，归因分 0.7731，单一权威（未交叉核实））
  - 候选：The Frantic White House Push to Get Jensen Huang Back（事前或同步，归因分 0.7115，单一权威（未交叉核实））

### 标的异动（按异动程度）

| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 核验 |
| --- | --- | --- | --- | --- | --- | --- |
| SOL/USDT | -7.41% / -2.29 | 2026-11-24 23:00 UTC+8  窗口 -0.96% | 比特币ETF出现5.7亿美元净流出，导致比特币跌破6万美元，并可能引发了加密货币市场的普遍下跌。 | 0.72 | 事前或同步 | 单源未核实 |
| ADA/USDT | -6.45% / -1.79 | 2026-11-24 23:00 UTC+8  窗口 -1.10% | 比特币ETF出现5.7亿美元净流出，导致比特币跌破6万美元，并可能引发了加密货币市场的普遍下跌。 | 0.72 | 事前或同步 | 单源未核实 |
| XRP/USDT | -6.44% / -2.20 | 2026-11-24 00:00 UTC+8  窗口 -3.51% | 未找到明确新闻，可能为流动性/清算/技术面 | 0.00 | 无明显新闻 | — |
| DOGE/USDT | -5.93% / -1.84 | 2026-11-24 23:00 UTC+8  窗口 -0.97% | 比特币ETF出现5.7亿美元净流出，导致比特币跌破6万美元，并可能引发了加密货币市场的普遍下跌。 | 0.72 | 事前或同步 | 单源未核实 |
| NVDA | -5.94% / -0.69 | 2026-11-24 22:30 UTC+8  窗口 -6.25% | 未找到明确新闻，可能为流动性/清算/技术面 | 0.00 | 无明显新闻 | — |
| ETH/USDT | -5.74% / -1.81 | 2026-11-24 01:00 UTC+8  窗口 -1.50% | 未找到明确新闻，可能为流动性/清算/技术面 | 0.00 | 无明显新闻 | — |
| BTC/USDT | -4.55% / -1.98 | 2026-11-24 10:00 UTC+8  窗口 -1.66% | 美股下跌，因英伟达（Nvidia）的上涨势头消退，美元下跌。 | 0.77 | 事前或同步 | 单源未核实 |
| BNB/USDT | -3.75% / -1.42 | 2026-11-24 10:00 UTC+8  窗口 -1.47% | 美股下跌，因英伟达（Nvidia）的上涨势头消退，美元下跌。 | 0.77 | 事前或同步 | 单源未核实 |

### 辅助：新闻中心热榜 Top 10（价格不参与排序）

| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Jensen Huang Is Back at Nvidia. Here’s What to Know. | TRADFI | 89.59 | 多源确认 | 2026-11-24 02:23 UTC+8 | NVDA: 24h -7.23% | Ab24h -6.54% | 锚定 165.165 | 仅展示，不参与排序 |
| 2 | Why Nvidia Needed Jensen Huang Back—And What His Return Really Changes | TRADFI | 82.143 | 多源确认 | 2026-11-24 03:57 UTC+8 | NVDA: 24h -5.88% | Ab24h -5.38% | 锚定 165.185 | 仅展示，不参与排序 |
| 3 | Bitcoin slips back toward $60,000 as Jensen Huang’s Nvidia return rally fizzles | TRADFI | 70.074 | 多源确认 | 2026-11-24 14:21 UTC+8 | NVDA: 24h 窗口未结束（锚定 152.455，aligned_next_bar(+8.1h); 24h_window_pending） |
| 4 | Bitcoin ETF Outflows Set Monthly Record at $4.71 Billion | TRADFI | 64.036 | 单一权威（未交叉核实） | 2026-11-24 20:30 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 60014.6，24h_window_pending） |
| 5 | Trump faces backlash after saying he 'convinced' Nvidia to reinstate CEO Jensen Huang | TECH_AI | 61.329 | 多源确认 | 2026-11-24 18:53 UTC+8 | NVDA: 24h 窗口未结束（锚定 152.455，aligned_next_bar(+3.6h); 24h_window_pending） |
| 6 | Bitcoin Fails to Hold Nvidia Bump With Crypto Headwinds in Focus | CRYPTO | 58.739 | 多源确认 | 2026-11-24 19:02 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 60484.95，24h_window_pending） |
| 7 | BlackRock opens tokenized money market fund with $100 million in assets to Hong Kong investors | TRADFI | 53.167 | 多源确认 | 2026-11-24 21:17 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 60440.0，24h_window_pending） |
| 8 | $14.7B in ‘Lost’ Bitcoin Has Moved Since 2018: Report | CRYPTO | 48.396 | 多源确认 | 2026-11-24 20:40 UTC+8 | BTC/USDT: 24h 窗口未结束（锚定 60014.6，24h_window_pending） |
| 9 | Tom Lee Says Ethereum Is as Scarce as Bitcoin—And Bitmine Just Bought More | CRYPTO | 45.264 | 多源确认 | 2026-11-24 00:46 UTC+8 | BTC/USDT: 24h -2.54% | Ab24h +0.77% | 锚定 61674.18 | 仅展示，不参与排序 |
| 10 | Trump reportedly called into Nvidia board meeting to advocate for Huang’s return | TECH_AI | 40.533 | 单源未核实 | 2026-11-24 00:39 UTC+8 | NVDA: 24h -7.06% | Ab24h -6.39% | 锚定 165.1301 | 仅展示，不参与排序 |

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
- 本次调用 8 次，输入 5437 / 输出 466 tokens，目录价 $0.0007。
- 事件语料主要来自已跑通的 BTC/USDT 与 NVDA 时间线，山寨币/宽基指数的直接新闻覆盖有限，无候选或低分时会明确标注「未找到明确新闻」。
- 美股以 Yahoo 1h/15m K 线为准；UTC+8 日界下，美股常规交易多在当晚 22:30 开盘、次日 05:00 收盘（EST）。
