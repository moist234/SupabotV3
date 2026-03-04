# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Supabot V3 is a fully automated algorithmic trading system that detects accelerating social media buzz (Twitter/Reddit) on stocks in early-stage price action ("Fresh": -5% to +5% 7-day change) and executes 7-day paper trades. Validated on 258 trades with 67.8% win rate, p<0.001 significance.

## Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# Run main scan (sells 7-day positions, scans universe, places paper trades, outputs CSV, sends Discord)
python3 supabot_v3.py

# Update Google Sheets (run after main scan; reads latest CSV from outputs/)
python3 auto_sheet.py

# Analysis tools
python3 ultimate_supabot_analyzer.py        # 14-module diagnostics on historical_trades.csv
python3 edge_decay_analyzer.py              # Signal decay analysis (terminal only)
python3 v4_reranking_analysis.py            # Validates V4 weights out-of-sample
python3 generate_performance_stats.py       # Performance summary stats
```

The system runs automatically via GitHub Actions daily at 2 PM EST (`.github/workflows/supabot-v3-scan.yml`). Manual trigger is also available.

## Architecture

### Core Files

**`supabot_v3.py`** — Main engine (1,161 lines). Contains the full pipeline:
- Constants at top (lines 35-46): `FRESH_MIN/MAX`, `MIN_MARKET_CAP`, buzz thresholds, `POSITION_VALUE=$500`
- Technical metric calculators (lines 48-210): Bollinger position, ATR, volume trend, RSI, earnings proximity, 52w positioning
- `calculate_quality_score_v4()` (lines 214-364): **Active scoring system** — `calculate_quality_score()` is legacy/tracking only
- `get_universe()`: Fetches ~400 stocks from Finviz (Market Cap +Small, Avg Vol >500K, Price >$5, Rel Vol >0.5)
- `scan()` (lines 758-1006): Core selection logic — universe → hard filters → Fresh → Relative Fresh → buzz → V4 score
- `sell_seven_day_positions()` / `place_paper_trades()`: Alpaca paper trading execution
- `send_discord_notification()`: Rich embed alerts

**`auto_sheet.py`** — Google Sheets integration (501 lines):
- Reads latest CSV from `outputs/`, writes 25-column rows to "SupabotV3" sheet
- Auto-fills exit prices for trades ≥7 days old via yfinance
- Calculates batch summaries (win rate, avg return, vs S&P)

### V4 Scoring System (Active)

Selection threshold: V4 ≥100 (expected 78-80% WR). If fewer than 3 quality picks exist, takes top 3 by V4 score regardless — "never sit out" philosophy.

Score components (max ~215 points):
- **Fresh %** (0-50 pts): Sweet spots at 1-2% (80.4% WR) and 4-5% (87.5% WR)
- **Short Interest** (0-40 pts): 3-7% zone = 40 pts (71.9% WR); >20% = hard skip
- **Market Cap** (0-35 pts): Large = 35 pts (77.1% WR); Small = 0 pts + hard skip (46.2% WR)
- **Sector** (0-25 pts): Basic Materials = 25 pts (81.5% WR)
- **Volume Spike** (0-15 pts): Ratio >1.5 = 15 pts
- **Earnings Proximity** (0-15 pts): 30-60 day window = 15 pts (88.9% WR); <30d from earnings = hard skip
- **Institutional Ownership** (0-10 pts): <30% on Large/Mid = 10 pts; >90% = hard skip in Risk-On
- **Combination Bonus** (0-10 pts): Fresh 1-3% + SI 2-5% = 10 pts

### Key Filters and Logic

- **Banned sectors**: Energy, Consumer Cyclical, Utilities, Financial Services
- **Relative Fresh**: Stock 7d% minus SPY 7d% must be >0.5% (prevents momentum chasing)
- **Regime detection**: Risk-On when SPY close > 20-day SMA; affects institutional ownership filter
- **7-day cooldown**: `recent_picks.json` prevents same ticker within 7 days

### Data Flow

```
GitHub Actions (2 PM EST)
  → sell_seven_day_positions() [check alpaca_positions.json, sell via Alpaca]
  → scan() [Finviz universe → filters → V4 score → select picks]
  → place_paper_trades() [$500/stock on Alpaca paper trading]
  → save_picks() [CSV to outputs/]
  → send_discord_notification()
  → auto_sheet.py [write to Google Sheets, update exits, batch summaries]
  → git commit alpaca_positions.json [skip ci]
```

### State Files

- **`alpaca_positions.json`** — Active positions with entry dates; auto-committed by GitHub Actions after each scan
- **`recent_picks.json`** — 7-day cooldown tracker
- **`outputs/`** — CSVs named `supabot_v3_scan_YYYY-MM-DD_HHMM.csv`
- **`historical_trades.csv`** — 258-trade backtest dataset used by analysis tools

### Credentials

API keys are loaded from `.env` (never commit). GitHub Actions uses repository secrets. Google Sheets uses `service_account.json` (never commit). Keys needed: Reddit, twitterapi.io, Discord webhook, Finnhub, Alpaca (paper), Alpha Vantage.
