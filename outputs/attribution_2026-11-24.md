# 异动归因榜（以价格异动为起点反查新闻）

日界为 **UTC+8（Asia/Kuala_Lumpur）**。价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。

排序/候选公式：

`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`

窗口取跳变起点前 6h 至后 1h；晚于跳变的新闻标记为「事后解释/报道」并降低时间权。

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

## 花费与局限

- LLM 模型：`google/gemini-2.5-flash-lite`，仅对上榜异动/共同因子的 Top 候选调用。
