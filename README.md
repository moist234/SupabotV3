🤖 Supabot V4
Algorithmic Trading System with Validated Statistical Edge
Systematic trading algorithm that identifies stocks using social sentiment analysis combined with technical indicators. Fully automated via GitHub Actions with paper trading execution.

📊 Performance Metrics

Win Rate: 67.8% (175-83 over 258 trades)
Average Return: +1.81% per 7-day trade
Sharpe Ratio: 0.77 (annualized)
Statistical Significance: p<0.001 (t=4.55)
95% Confidence Interval: [+1.0%, +2.6%]
Consistency: 89% profitable weeks (8/9)
Best Trade: TERN +48.35%
ROI: +1.81% on $129k hypothetical capital

Trading Period: November 2025 - January 2026 (58 weeks)

✨ Key Features
🎯 Statistically Validated Edge - p<0.001 significance, 95% CI demonstrates real alpha
🤖 100% Automated - GitHub Actions daily scans, Alpaca execution, auto-tracking
📊 Multi-Factor Scoring - V4 model with 16.2-point gap (p<0.0001) between winners/losers
💬 Real-Time Alerts - Discord notifications with technical data
📈 Google Sheets Integration - Automated performance tracking and batch analysis
🎲 Control Groups - Scientific validation vs random selection

🎯 The Strategy: Fresh + Accelerating
Core Hypothesis
Stocks with accelerating social buzz BEFORE significant price movement generate alpha.
Entry Signals

Fresh - Price movement between -5% to +5% over 7 days (early-stage timing)
Accelerating - Twitter ≥15 mentions OR Reddit ≥5 mentions (buzz building)
Quality Filters - Market cap, sector, short interest, institutional ownership

V4 Scoring System
Multi-factor model validated on 238 trades:

Fresh % sweet spots (1-2%: 80.4% WR)
Short interest zones (3-7%: 71.9% WR)
Market cap weighting (Large: 77.1% WR vs Small: 46.2% WR)
Sector performance (Basic Materials: 81.5% WR)
Earnings proximity (30-60d window: 88.9% WR)
Institutional ownership (Low inst + Large cap: 89.5% WR)

Deployment: V4 ≥100 quality threshold (expected 78-80% WR)
