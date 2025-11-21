"""
Supabot V2 - Main Scanner with Market Regime Filter
REQUIRES: Fresh + Accelerating (validated 70% WR)
EXCLUDES: Squeeze signals (validated 22% WR, toxic)
PAUSES: When market conditions unfavorable (VIX >20, SPY down >3%)
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
from typing import List, Dict
from datetime import datetime
import pandas as pd
import yfinance as yf

from config import SCANNER_CONFIG, ENABLE_AI_ANALYSIS, DISCORD_WEBHOOK_URL
from data.market_data import get_stock_info, get_price_changes, get_float_analysis, get_short_interest
from data.technical_analysis import get_technical_analysis
from data.social_signals import get_quality_universe, get_social_intelligence
from filters.quality_filter import passes_all_quality_filters
from filters.price_action_filter import passes_all_price_action_filters, is_fresh_signal
from analysis.ai_analyzer import AIAnalyzer

# MARKET REGIME THRESHOLDS
MAX_VIX = 20.0
MAX_SPY_10D_DROP = -3.0
MAX_SPY_5D_DROP = -2.0
MAX_RED_WEEKS = 3


def check_market_regime() -> dict:
    """Check if market favorable for Fresh+Accel mean reversion strategy."""
    
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="2mo")
        
        if hist.empty:
            return {'is_tradeable': True, 'status': '⚠️ No data', 'reasons': []}
        
        close = hist['Close']
        volume = hist['Volume']
        
        spy_5d = ((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100) if len(close) > 5 else 0
        spy_10d = ((close.iloc[-1] - close.iloc[-11]) / close.iloc[-11] * 100) if len(close) > 10 else 0
        
        current_vol = volume.iloc[-1]
        avg_vol_20d = volume.tail(20).mean()
        spy_volume_ratio = current_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0
        
        red_weeks = 0
        for i in range(1, min(5, len(close) // 5)):
            week_start = close.iloc[-(i*5 + 5)]
            week_end = close.iloc[-(i*5)]
            if week_end < week_start:
                red_weeks += 1
            else:
                break
        
        try:
            vix_ticker = yf.Ticker("^VIX")
            vix_hist = vix_ticker.history(period="5d")
            vix = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 0
        except:
            vix = 0
        
        reasons = []
        is_tradeable = True
        
        if vix > MAX_VIX:
            is_tradeable = False
            reasons.append(f"High volatility (VIX: {vix:.1f} > {MAX_VIX})")
            reasons.append("Mean reversion fails in high-vol regimes")
        
        if spy_10d < MAX_SPY_10D_DROP:
            is_tradeable = False
            reasons.append(f"Sustained downtrend (SPY 10d: {spy_10d:.1f}% < {MAX_SPY_10D_DROP}%)")
            reasons.append("Macro flow overwhelming micro signals")
        
        if spy_5d < MAX_SPY_5D_DROP:
            is_tradeable = False
            reasons.append(f"Sharp recent decline (SPY 5d: {spy_5d:.1f}% < {MAX_SPY_5D_DROP}%)")
        
        if red_weeks >= MAX_RED_WEEKS:
            is_tradeable = False
            reasons.append(f"Extended selling ({red_weeks} red weeks)")
        
        if spy_5d < 0 and spy_volume_ratio > 1.3:
            is_tradeable = False
            reasons.append(f"High-volume distribution ({spy_volume_ratio:.2f}x)")
        
        if is_tradeable:
            status = "✅ MARKET FAVORABLE"
            reasons.insert(0, "Low-vol regime (optimal for mean reversion)")
        else:
            status = "🚨 MARKET UNFAVORABLE - PAUSED"
        
        return {
            'is_tradeable': is_tradeable,
            'status': status,
            'reasons': reasons,
            'spy_5d': round(spy_5d, 2),
            'spy_10d': round(spy_10d, 2),
            'vix': round(vix, 2),
            'spy_volume_ratio': round(spy_volume_ratio, 2),
            'red_weeks': red_weeks
        }
    
    except Exception as e:
        return {'is_tradeable': True, 'status': '⚠️ Error', 'reasons': [str(e)]}


def send_paused_notification():
    """Send Discord when V2 paused."""
    
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        from discord_webhook import DiscordWebhook, DiscordEmbed
        
        regime = check_market_regime()
        
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, username="Supabot V2 Watch")
        
        embed = DiscordEmbed(
            title="🚨 Supabot V2 - Strategy Paused",
            description="Market regime unfavorable for Fresh+Accel edge",
            color='ff6600'
        )
        
        embed.add_embed_field(
            name="📊 Market Metrics",
            value=f"VIX: {regime['vix']:.1f} | SPY 10d: {regime['spy_10d']:+.1f}% | SPY 5d: {regime['spy_5d']:+.1f}%",
            inline=False
        )
        
        embed.add_embed_field(
            name="⚠️ Pause Reasons",
            value="\n".join(f"• {r}" for r in regime['reasons'][:3]),
            inline=False
        )
        
        embed.add_embed_field(
            name="📈 Historical Context",
            value="**VIX < 18:** 84% WR, +5.2% avg\n**VIX > 20:** 28% WR, -2.1% avg",
            inline=False
        )
        
        embed.set_footer(text=f"V2 Paused | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        
        webhook.add_embed(embed)
        webhook.execute()
    
    except Exception as e:
        print(f"⚠️ Discord failed: {e}")


class SupabotScanner:
    """Main scanner with regime awareness."""
    
    def __init__(self):
        self.ai_analyzer = AIAnalyzer() if ENABLE_AI_ANALYSIS else None
        self.scan_results = []
        self.filtered_results = []
    
    def scan(self, custom_tickers: List[str] = None, top_k: int = None) -> pd.DataFrame:
        """Run scan with market regime check."""
        
        top_k = top_k or SCANNER_CONFIG.top_k
        
        print("\n" + "="*70)
        print("🤖 SUPABOT V2 - REGIME-AWARE SCANNER")
        print("="*70)
        
        # CHECK MARKET REGIME FIRST
        regime = check_market_regime()
        
        print("\n📊 MARKET REGIME ANALYSIS")
        print("="*70)
        print(f"   SPY 5d:  {regime['spy_5d']:+.1f}%")
        print(f"   SPY 10d: {regime['spy_10d']:+.1f}%")
        print(f"   VIX:     {regime['vix']:.1f}")
        print(f"   Volume:  {regime['spy_volume_ratio']:.2f}x")
        if regime['red_weeks'] > 0:
            print(f"   Streak:  {regime['red_weeks']} red weeks")
        print()
        print(f"   {regime['status']}")
        print()
        
        for reason in regime['reasons']:
            print(f"   └─ {reason}")
        
        if not regime['is_tradeable']:
            print()
            print("   ⏸️  Strategy will resume when:")
            print("      ✅ VIX < 20")
            print("      ✅ SPY 10d > -2%")
            print()
            print("   💡 Why Fresh+Accel needs stable markets:")
            print("      └─ Mean reversion strategy (requires low vol)")
            print("      └─ Buzz must overpower price action")
            print("      └─ Downtrends break mean-reversion edge")
            print()
            print("   📊 Historical:")
            print("      └─ VIX <18: 84% WR (Weeks 1-9)")
            print("      └─ VIX >20: 28% WR (Weeks 10-13)")
        
        print("="*70 + "\n")
        
        if not regime['is_tradeable']:
            print("🚨 Market unfavorable - Scan paused")
            print("   Sending Discord notification...\n")
            send_paused_notification()
            return pd.DataFrame()  # Return empty
        
        # Market is good - proceed with scan
        print("✅ Market favorable - Proceeding with scan\n")
        
        # ... REST OF YOUR EXISTING V2 SCAN CODE ...
        # (Keep all the existing filtering logic from your current scanner.py)
        
        print(f"\n📊 Step 1: Getting quality universe...")
        universe = custom_tickers if custom_tickers else get_quality_universe()
        universe = universe[:SCANNER_CONFIG.scan_limit]
        print(f"   → {len(universe)} stocks in universe")
        
        print(f"\n🔍 Step 2: Quality filtering...")
        quality_passed = self._filter_by_quality(universe)
        print(f"   → {len(quality_passed)} passed quality filters")
        
        if len(quality_passed) == 0:
            print("\n❌ No stocks passed quality filters!")
            return pd.DataFrame()
        
        print(f"\n📈 Step 3: Price action filtering...")
        price_action_passed = self._filter_by_price_action(quality_passed)
        print(f"   → {len(price_action_passed)} passed price action filters")
        
        if len(price_action_passed) == 0:
            print("\n❌ No stocks passed price action filters!")
            return pd.DataFrame()
        
        print(f"\n🌐 Step 4: Analyzing social signals...")
        social_scored = self._analyze_social_signals(price_action_passed)
        print(f"   → {len(social_scored)} stocks with social activity")
        
        print(f"\n📊 Step 5: Running technical analysis...")
        technical_scored = self._analyze_technicals(social_scored)
        
        if ENABLE_AI_ANALYSIS and self.ai_analyzer:
            print(f"\n🤖 Step 6: Running AI analysis...")
            ai_analyzed = self._run_ai_analysis(technical_scored)
        else:
            print(f"\n⚠️  Step 6: AI analysis disabled")
            ai_analyzed = technical_scored
        
        print(f"\n🏆 Step 7: Scoring and ranking...")
        final_scores = self._calculate_final_scores(ai_analyzed)
        
        df = pd.DataFrame(final_scores)
        
        if df.empty:
            print("\n❌ No candidates after scoring!")
            return pd.DataFrame()
        
        df = df.sort_values('composite_score', ascending=False)
        df = df[df['composite_score'] >= SCANNER_CONFIG.min_composite_score]
        df = df[df['is_fresh'] == True]
        
        if df.empty:
            print("   ⚠️  No fresh signals found")
            return pd.DataFrame()
        
        top_candidates = df.head(top_k)
        
        print(f"\n✅ Found {len(top_candidates)} high-quality candidates!")
        print("="*70 + "\n")
        
        return top_candidates
    
    # Keep all your existing methods
    def _filter_by_quality(self, tickers: List[str]) -> List[Dict]:
        """Filter tickers by fundamental quality."""
        passed = []
        
        for ticker in tickers:
            try:
                stock_data = get_stock_info(ticker)
                if not stock_data:
                    continue
                
                passes, reason = passes_all_quality_filters(stock_data)
                
                if passes:
                    passed.append({
                        'ticker': ticker,
                        'stock_data': stock_data
                    })
            except Exception as e:
                continue
        
        return passed
    
    def _filter_by_price_action(self, stocks: List[Dict]) -> List[Dict]:
        """Filter by price action."""
        passed = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                stock_data = stock['stock_data']
                
                price_changes = get_price_changes(ticker)
                stock_data.update(price_changes)
                
                technical = get_technical_analysis(ticker)
                
                passes, reason = passes_all_price_action_filters(price_changes, technical)
                
                if not passes:
                    print(f"   ✗ {ticker}: {reason}")
                
                if passes:
                    is_fresh = is_fresh_signal(
                        price_changes.get('change_7d', 0),
                        price_changes.get('change_90d', 0)
                    )
                    
                    passed.append({
                        'ticker': ticker,
                        'stock_data': stock_data,
                        'price_changes': price_changes,
                        'technical': technical,
                        'is_fresh': is_fresh
                    })
            except Exception as e:
                continue
        
        return passed
    
    def _analyze_social_signals(self, stocks: List[Dict]) -> List[Dict]:
        """Analyze social signals."""
        results = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                social = get_social_intelligence(ticker)
                
                if social.get('composite_score', 0) > 0.2:
                    stock['social'] = social
                    results.append(stock)
            except Exception as e:
                stock['social'] = {'composite_score': 0.0}
                results.append(stock)
        
        return results
    
    def _analyze_technicals(self, stocks: List[Dict]) -> List[Dict]:
        """Run technical analysis."""
        for stock in stocks:
            if 'technical' not in stock:
                try:
                    stock['technical'] = get_technical_analysis(stock['ticker'])
                except:
                    stock['technical'] = {'technical_score': 3.0}
        return stocks
    
    def _run_ai_analysis(self, stocks: List[Dict]) -> List[Dict]:
        """Run AI analysis."""
        for stock in stocks:
            try:
                ticker = stock['ticker']
                ai_result = self.ai_analyzer.analyze_stock(
                    ticker,
                    stock['stock_data'],
                    stock['social'],
                    stock['technical']
                )
                stock['ai_analysis'] = ai_result
            except Exception as e:
                stock['ai_analysis'] = {
                    'rating': 'HOLD',
                    'composite_score': 3.0
                }
        return stocks
    
    def _calculate_final_scores(self, stocks: List[Dict]) -> List[Dict]:
        """Calculate final scores (keep your existing logic)."""
        
        # Import enhanced modules
        try:
            from data.fundamentals import get_financial_statements, calculate_advanced_valuation, calculate_quality_score
            from data.news_events import get_catalyst_summary
            from data.insider_activity import get_insider_trades
            has_enhanced_data = True
        except:
            has_enhanced_data = False
        
        results = []
        
        for stock in stocks:
            try:
                ticker = stock['ticker']
                stock_data = stock['stock_data']
                price_changes = stock.get('price_changes', {})
                social = stock.get('social', {})
                technical = stock.get('technical', {})
                ai_analysis = stock.get('ai_analysis', {})
                
                is_fresh = stock.get('is_fresh', False)
                is_accelerating = social.get('is_accelerating', False)
                
                if not (is_fresh and is_accelerating):
                    continue
                
                float_data = get_float_analysis(ticker)
                short_data = get_short_interest(ticker)
                
                has_squeeze = short_data.get('squeeze_potential', False)
                short_percent = short_data.get('short_percent', 0)
                
                if has_squeeze or short_percent > 20:
                    print(f"   ✗ {ticker}: Squeeze {short_percent:.0f}% - EXCLUDED")
                    continue
                
                if ENABLE_AI_ANALYSIS and 'composite_score' in ai_analysis:
                    base_composite = ai_analysis['composite_score']
                else:
                    base_composite = 3.5
                
                result = {
                    'ticker': ticker,
                    'price': stock_data.get('price', 0),
                    'market_cap': stock_data.get('market_cap', 0),
                    'sector': stock_data.get('sector', 'Unknown'),
                    'change_7d': price_changes.get('change_7d', 0),
                    'is_fresh': is_fresh,
                    'is_accelerating': is_accelerating,
                    'x_mentions': social.get('x_recent_mentions', 0),
                    'reddit_mentions': social.get('reddit_total_mentions', 0),
                    'composite_score': base_composite,
                    'rating': ai_analysis.get('rating', 'HOLD'),
                    'conviction': ai_analysis.get('conviction', 'MEDIUM'),
                    'position_size': 'half',
                    'stop_loss': stock_data.get('price', 0) * 0.92,
                    'hold_period': '7 days',
                }
                
                results.append(result)
            
            except:
                continue
        
        return results


def run_scan(custom_tickers: List[str] = None, top_k: int = None) -> pd.DataFrame:
    """Convenience function to run a scan."""
    scanner = SupabotScanner()
    return scanner.scan(custom_tickers=custom_tickers, top_k=top_k)


if __name__ == "__main__":
    print("\n🤖 Supabot V2 - Regime-Aware Fresh+Accel Scanner\n")
    
    # Run scan (includes regime check)
    results = run_scan(top_k=5)
    
    if not results.empty:
        print("\n✅ V2 scan complete - sending to Discord...")
        
        from discord_notify import send_scan_results
        send_scan_results(results, {'scanned': SCANNER_CONFIG.scan_limit})
    else:
        print("\n⏸️ V2 scan paused or no picks found\n")