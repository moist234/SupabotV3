"""
Supabot V2 - Centralized Configuration
All settings in one place for easy tuning.
"""
import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()

# ============ API Keys ============
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "supabot/2.0")

TWITTER_API_KEY = os.getenv("TWITTERAPI_IO_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ============ Mode Settings ============
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"
USE_X_SIGNAL = os.getenv("USE_X_SIGNAL", "true").lower() == "true"
ENABLE_AI_ANALYSIS = os.getenv("ENABLE_AI_ANALYSIS", "true").lower() == "true"

# ============ Scanner Configuration ============
@dataclass
class ScannerConfig:
    """Main scanner settings - tune these to adjust risk/quality."""
    
    # How many stocks to process
    scan_limit: int = 100          # Scan top 100 trending tickers
    top_k: int = 3                # Return best 5 candidates
    
    # Market cap filters ($USD)
    min_market_cap: float = 500_000_000      # Make sure this line exists
    max_market_cap: float = 999_999_999_999_999  # Make sure this line exists
    # Price filters
    min_price: float = 5.00
    max_price: float = 9999.00
    # Liquidity requirements
    min_daily_volume_usd: float = 2_000_000  # $2M daily volume
    min_avg_volume: int = 500_000            # 500k shares average
    
    # Price action filters (CRITICAL for avoiding chasing)
    max_7d_change: float = 20.0    # Skip if up >20% in 7 days
    min_90d_change: float = 0.0    # Must be in uptrend (0%+ over 90d)
    max_1d_change: float = 12.0    # Skip daily spikes >12%
    fresh_min: float = -5.0        # Fresh range: -5% to +10%
    fresh_max: float = 5.0
    
    # Social signal thresholds
    min_x_mentions: int = 10       # Minimum X/Twitter posts
    min_reddit_mentions: int = 5   # Minimum Reddit mentions
    min_total_mentions: int = 15   # Total across platforms
    
    # Technical requirements
    min_rsi: float = 40.0          # Not oversold
    max_rsi: float = 75.0          # Not overbought
    min_volume_ratio: float = 0.5  # Allow below-average volume (quality stocks don't always spike)
    
    # Fundamental quality gates
    min_revenue_growth: float = 5.0        # 5% YoY growth minimum
    max_pe_ratio: float = 60.0             # Not insanely overvalued
    require_positive_earnings: bool = False # Set True to require profit
    
    # Scoring thresholds
    min_composite_score: float = 3.0       # Minimum 3.5/5.0 to pass
    min_fundamental_score: float = 2.8     # Min fundamentals
    min_technical_score: float = 3.0       # Min technical setup
    
    # Reddit configuration
    reddit_lookback_hours: int = 24        # Scan last 24 hours
    reddit_baseline_days: int = 5          # Historical baseline
    reddit_limit_per_sub: int = 80         # Posts per subreddit

# ============ AI Analysis Configuration ============
@dataclass
class AIConfig:
    """AI master prompts - which analyses to run."""
    
    # Enable/disable each master prompt
    enable_360_scanner: bool = True        # Market/sector analysis
    enable_risk_assessment: bool = True    # Pre-mortem risk analysis
    enable_technical_analysis: bool = True # Chart patterns, indicators
    enable_value_analysis: bool = True     # Value investing perspective
    enable_sentiment_analysis: bool = True # Social sentiment gauge
    enable_geopolitical: bool = False      # Geopolitical risks (optional)
    
    # Weights for composite score calculation
    fundamental_weight: float = 0.35       # 35% fundamentals
    technical_weight: float = 0.25         # 25% technicals
    sentiment_weight: float = 0.20         # 20% sentiment
    risk_penalty_weight: float = 0.20      # 20% risk penalty
    
    # AI call settings
    temperature: float = 0.3               # Lower = more consistent
    max_retries: int = 3                   # Retry failed calls
    timeout_seconds: int = 30              # API timeout

# ============ Risk Management ============
@dataclass
class RiskConfig:
    """Position sizing and risk management rules."""
    
    # Position sizing by conviction
    high_conviction_size: float = 0.10     # 10% for high conviction
    medium_conviction_size: float = 0.05   # 5% for medium conviction
    low_conviction_size: float = 0.025     # 2.5% for low conviction
    
    # Stop loss rules
    default_stop_loss_pct: float = 0.10    # -10% default stop
    tight_stop_loss_pct: float = 0.07      # -7% for parabolic plays
    wide_stop_loss_pct: float = 0.12       # -12% for value plays
    
    # Portfolio constraints
    max_portfolio_risk: float = 0.25       # Max 25% at risk
    max_positions: int = 5                 # Max 5 open positions
    
    # Hold period recommendations
    intraday_max_days: int = 2             # Parabolic plays
    swing_trade_days: int = 14             # 2 weeks
    position_trade_days: int = 60          # 2 months

# ============ Subreddit Configuration ============
REDDIT_SUBREDDITS = [
    "wallstreetbets",
    "ValueInvesting" 
    "smallstreetbets",
    "Shortsqueeze",
    "StockMarket",
    "stocks",
    "investing",
    "daytrading",
    "options"
]

# Subreddit weights (importance multipliers)
SUBREDDIT_WEIGHTS = {
    "wallstreetbets": 1.0,      # Highest weight
    "options": 0.9,
    "ValueInvesting": 0.9,
    "smallstreetbets": 0.9,
    "Shortsqueeze": 0.85,
    "daytrading": 0.7,
    "stocks": 0.3,              # Lower weight (less actionable)
}

# ============ Banned Sectors ============
# Add sectors you want to avoid
BANNED_SECTORS: List[str] = [
    # "Biotechnology",           # Often too volatile/unpredictable
    # "Drug Manufacturers",       # Binary events (FDA approvals)
    # "Medical Devices",
    # "Real Estate",             # Interest rate sensitive
]

# ============ Display Settings ============
@dataclass
class DisplayConfig:
    """Terminal output and Discord formatting."""
    
    # Rich terminal colors
    use_colors: bool = True
    show_detailed_output: bool = True
    
    # Discord notifications
    send_to_discord: bool = True
    send_jackpot_alerts: bool = True    # Special alerts for rare setups
    
    # Output directories
    output_dir: str = "outputs"
    log_dir: str = "logs"

# ============ Create Global Instances ============
SCANNER_CONFIG = ScannerConfig()
AI_CONFIG = AIConfig()
RISK_CONFIG = RiskConfig()
DISPLAY_CONFIG = DisplayConfig()

# ============ Validation ============
def validate_config():
    """Ensure critical settings are present."""
    errors = []
    
    if ENABLE_AI_ANALYSIS and not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY required when ENABLE_AI_ANALYSIS=true")
    
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        errors.append("Reddit API credentials missing")
    
    if SCANNER_CONFIG.min_price > SCANNER_CONFIG.max_price:
        errors.append("min_price cannot be greater than max_price")
    
    if SCANNER_CONFIG.min_market_cap > SCANNER_CONFIG.max_market_cap:
        errors.append("min_market_cap cannot be greater than max_market_cap")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"- {e}" for e in errors))
    
    return True

# Validate on import
if not MOCK_MODE:
    validate_config()

# ============ Helper Functions ============
def get_config_summary() -> str:
    """Return human-readable config summary."""
    return f"""
╔══════════════════════════════════════════════════════════╗
║              SUPABOT V2 CONFIGURATION                    ║
╚══════════════════════════════════════════════════════════╝

Mode: {'MOCK (Testing)' if MOCK_MODE else 'LIVE'}
AI Analysis: {'ENABLED' if ENABLE_AI_ANALYSIS else 'DISABLED'}
Model: {OPENAI_MODEL}

Scanner Settings:
  • Scan Limit: {SCANNER_CONFIG.scan_limit} tickers
  • Return Top: {SCANNER_CONFIG.top_k} candidates
  • Market Cap: ${SCANNER_CONFIG.min_market_cap/1e6:.0f}M - ${SCANNER_CONFIG.max_market_cap/1e6:.0f}M
  • Price Range: ${SCANNER_CONFIG.min_price:.2f} - ${SCANNER_CONFIG.max_price:.2f}
  • Min Daily Volume: ${SCANNER_CONFIG.min_daily_volume_usd/1e6:.1f}M

Filters:
  • Max 7d Change: {SCANNER_CONFIG.max_7d_change:.0f}%
  • Min 90d Change: {SCANNER_CONFIG.min_90d_change:.0f}%
  • Fresh Range: {SCANNER_CONFIG.fresh_min:.0f}% to {SCANNER_CONFIG.fresh_max:.0f}%

Risk Management:
  • High Conviction: {RISK_CONFIG.high_conviction_size*100:.0f}%
  • Medium Conviction: {RISK_CONFIG.medium_conviction_size*100:.0f}%
  • Low Conviction: {RISK_CONFIG.low_conviction_size*100:.0f}%
  • Default Stop Loss: -{RISK_CONFIG.default_stop_loss_pct*100:.0f}%

AI Weights:
  • Fundamentals: {AI_CONFIG.fundamental_weight*100:.0f}%
  • Technicals: {AI_CONFIG.technical_weight*100:.0f}%
  • Sentiment: {AI_CONFIG.sentiment_weight*100:.0f}%
  • Risk Penalty: {AI_CONFIG.risk_penalty_weight*100:.0f}%
"""

if __name__ == "__main__":
    print(get_config_summary())