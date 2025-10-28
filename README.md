# 🤖 Supabot V2

**Quality-First AI Stock Scanner with Multi-Dimensional Analysis**

Supabot V2 is a professional-grade stock scanner that combines technical analysis, fundamental analysis, social intelligence, and AI-powered insights to find high-quality trading opportunities.

---

## ✨ Key Features

- 🎯 **Quality-First Universe** - Scans Finviz for stocks with real momentum (no penny stocks)
- 🧠 **6 AI Master Prompts** - Multi-dimensional analysis (360° scanner, risk assessment, technical, value, sentiment, geopolitical)
- 📊 **Institutional Data** - Financial statements, advanced valuation (EV/EBITDA, P/FCF), quality scoring
- 📰 **Catalyst Detection** - News analysis, earnings calendar, event tracking
- 🚀 **Smart Signals** - Fresh signals, buzz acceleration, parabolic setups, squeeze potential
- 🛡️ **Risk Management** - Specific stop losses, position sizing, hold periods
- 💬 **Discord Alerts** - Automated notifications with actionable recommendations
- ⚙️ **GitHub Actions** - Runs automatically 3x/day during market hours

---

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/YOUR_USERNAME/supabotv2.git
cd supabotv2
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and add your keys:

```properties
# Required
OPENAI_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
DISCORD_WEBHOOK_URL=your_webhook

# Optional (but recommended)
FINNHUB_API_KEY=your_key
FMP_API_KEY=your_key
TWITTERAPI_IO_KEY=your_key
```

### 3. Run Your First Scan

```bash
python agent_run.py
```

---

## 📊 How It Works

### Pipeline (7 Steps)

1. **Quality Universe** - Scans Finviz for 100-200 quality stocks with momentum
2. **Quality Filters** - Market cap ($500M-$50B), price ($5+), liquidity ($2M+ volume)
3. **Price Action Filters** - Removes pumped stocks (>20% in 7d), falling knives (<0% in 90d)
4. **Social Intelligence** - Checks buzz acceleration, catalyst mentions, quality discussions
5. **Technical Analysis** - RSI, moving averages, volume, chart patterns
6. **AI Analysis** - 6 master prompts analyze each candidate
7. **Score & Rank** - Composite scoring with quality/catalyst boosts

### Output

- 📋 Top 3-5 high-conviction candidates
- 🎯 Rating (STRONG_BUY, BUY, HOLD, AVOID)
- 💪 Conviction (HIGH, MEDIUM, LOW)
- 🛡️ Risk management (position size, stop loss, hold period)
- 📊 Detailed breakdown (fundamentals, valuation, catalysts)

---

## 🎯 Signal Guide

| Signal | Meaning | Action |
|--------|---------|--------|
| ✨ | **Fresh** - Buzz increasing but price <10% in 7d | Best entry timing |
| 📈 | **Accelerating** - Buzz increasing rapidly | Early momentum |
| 📰 | **Catalysts** - Real news (earnings, deals, etc.) | Fundamental driver |
| 💥 | **Parabolic** - Low float + high volume rotation | High volatility |
| 🚀 | **Squeeze** - High short interest (>20%) | Potential squeeze |
| 💎 | **Quality** - Strong fundamentals (margins, FCF, low debt) | Lower risk |
| 💰 | **Undervalued** - EV/EBITDA <12x | Value opportunity |

---

## ⚙️ Configuration

Edit `config.py` to tune filters:

```python
# Market cap range
min_market_cap: float = 500_000_000   # $500M minimum
max_market_cap: float = 50_000_000_000  # $50B maximum

# Price action filters
max_7d_change: float = 20.0  # Skip if already up >20%
min_90d_change: float = 0.0  # Must be in uptrend

# Scoring thresholds
min_composite_score: float = 3.5  # Only show 3.5+ scores
```

---

## 🤖 GitHub Actions (Automated Scans)

Runs automatically **3x per day** (Mon-Fri):
- 10:30 AM EST - After market open
- 1:00 PM EST - Mid-day
- 3:30 PM EST - Before close

**Manual trigger:** Actions tab → "Run workflow"

---

## 💰 Cost Estimate

**Per scan:**
- ~20 stocks analyzed
- 6 AI prompts per stock = 120 API calls
- Using GPT-4o-mini: ~$0.25 per scan

**Per month:**
- 3 scans/day × 22 trading days = 66 scans
- Total: ~$16.50/month

---

## 📖 Understanding Scores

### Composite Score (1-5 scale)

**Components:**
- 35% Fundamentals (revenue growth, margins, moat, quality)
- 25% Technicals (RSI, MA, volume, patterns)
- 20% Sentiment (news, social, contrarian opportunities)
- 20% Risk penalty

**Boosts:**
- +0.5 for high fundamental quality (margins >60%, positive FCF)
- +0.4 for strong catalysts (earnings beat, deals, upgrades)
- +0.3 for undervaluation (EV/EBITDA <10x)

**Penalties:**
- -0.2 for earnings risk (within 7 days)
- -0.3 for overvaluation (EV/EBITDA >30x)

### Ratings

- **4.5-5.0:** STRONG_BUY 🔥 (High conviction, full position)
- **3.8-4.4:** BUY ⚡ (Good setup, half position)
- **3.0-3.7:** HOLD (Wait for better entry)
- **2.5-2.9:** WEAK_HOLD (Low conviction)
- **<2.5:** AVOID (Skip this trade)

---

## 🛡️ Risk Management

**Position Sizing:**
- HIGH conviction: 10% of portfolio
- MEDIUM conviction: 5% of portfolio
- LOW conviction: 2.5% of portfolio

**Stop Losses:**
- Default: -10%
- Parabolic setups: -7% (tighter)
- Value plays: -12% (wider)

**Hold Periods:**
- Technical plays: 1-2 weeks
- Swing trades: 2-4 weeks
- Value opportunities: 1-3 months

---

## 📁 Project Structure

```
supabotv2/
├── config.py              # Central configuration
├── scanner.py             # Main orchestrator
├── agent_run.py           # Beautiful terminal UI
├── discord_notify.py      # Discord notifications
│
├── data/                  # Data layer
│   ├── market_data.py     # Prices, fundamentals
│   ├── technical_analysis.py  # RSI, MA, patterns
│   ├── social_signals.py  # Reddit, X/Twitter
│   ├── fundamentals.py    # Financial statements
│   └── news_events.py     # News, catalysts, earnings
│
├── analysis/              # AI engine
│   ├── ai_prompts.py      # 6 master prompts
│   └── ai_analyzer.py     # AI orchestrator
│
├── filters/               # Quality gates
│   ├── quality_filter.py  # Fundamental filters
│   └── price_action_filter.py  # Momentum filters
│
└── outputs/               # Scan results
```

---

## 🐛 Troubleshooting

**"No candidates found"**
- Market might be quiet - normal behavior
- Lower `min_composite_score` in config.py
- Check filter settings are not too strict

**"API rate limit"**
- Reduce scan_limit in config.py
- Add delays between API calls
- Upgrade to paid API tiers

**"Discord notifications not sending"**
- Verify DISCORD_WEBHOOK_URL in GitHub secrets
- Check webhook is valid in Discord server settings
- Look for error messages in workflow logs

---

## 📈 Performance Tips

**For better results:**
1. Run at market open (10:30 AM EST) for fresh setups
2. Focus on stocks with ✨ Fresh + 📰 Catalysts
3. Prioritize HIGH conviction plays only
4. Use stop losses religiously
5. Don't force trades when bot finds nothing

**For faster scans:**
1. Reduce scan_limit to 50
2. Disable geopolitical analysis (rarely needed)
3. Set MOCK_MODE=true for testing

---

## 🤝 Contributing

This is a personal trading tool. Use at your own risk.

---

## ⚠️ Disclaimer

This software is for educational purposes only. Not financial advice. 
Past performance does not guarantee future results. Trade at your own risk.

---

## 📞 Support

- Check logs in `logs/` directory
- Review GitHub Actions workflow logs
- Ensure all API keys are valid and have sufficient quota

**Built with ❤️ for better trading decisions**