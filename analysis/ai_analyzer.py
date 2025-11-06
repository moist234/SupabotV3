"""
Supabot V2 - AI Analyzer Engine
Orchestrates all 6 master prompts and synthesizes results.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from typing import Dict, Optional
from datetime import datetime

from config import OPENAI_API_KEY, OPENAI_MODEL, MOCK_MODE, AI_CONFIG
from analysis.ai_prompts import (
    PROMPT_360_SCANNER,
    PROMPT_RISK_ASSESSMENT,
    PROMPT_TECHNICAL,
    PROMPT_VALUE_INVESTOR,
    PROMPT_SENTIMENT,
    PROMPT_GEOPOLITICAL,
    build_prompt_context
)

# ============ AI Client ============

class AIAnalyzer:
    """
    Multi-dimensional AI stock analyzer.
    Orchestrates all 6 master prompts and synthesizes results.
    """
    
    def __init__(self):
        self.mock_mode = MOCK_MODE
        self.model = OPENAI_MODEL
        
        if not self.mock_mode:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=OPENAI_API_KEY)
            except Exception as e:
                print(f"Warning: OpenAI client initialization failed: {e}")
                self.client = None
        else:
            self.client = None
    
    def _call_llm(self, prompt: str, retry_count: int = 0) -> Dict:
        """
        Call OpenAI API with error handling and retries.
        
        Args:
            prompt: Formatted prompt string
            retry_count: Current retry attempt
        
        Returns:
            Parsed JSON response dict
        """
        if self.mock_mode or not self.client:
            return self._generate_mock_response(prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional financial analyst. Respond ONLY with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=AI_CONFIG.temperature,
                timeout=AI_CONFIG.timeout_seconds
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from markdown code blocks if present
            import re
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            return json.loads(content)
        
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            if retry_count < AI_CONFIG.max_retries:
                time.sleep(2)
                return self._call_llm(prompt, retry_count + 1)
            return {}
        
        except Exception as e:
            print(f"LLM call failed: {e}")
            if retry_count < AI_CONFIG.max_retries:
                time.sleep(2)
                return self._call_llm(prompt, retry_count + 1)
            return {}
    
    def _generate_mock_response(self, prompt: str) -> Dict:
        """Generate realistic mock responses for testing."""
        
        if "360" in prompt or "Market Scanner" in prompt:
            return {
                "growth_drivers": ["AI adoption accelerating", "Platform expansion", "Pricing power"],
                "major_headwinds": ["Competition intensifying", "Valuation concerns", "Macro headwinds"],
                "competitive_position": "Strong moat with network effects and switching costs",
                "recent_catalysts": "Recent earnings beat and guidance raise",
                "bull_case": "Growing addressable market. Strong execution on product roadmap. Expanding margins as scale increases.",
                "bear_case": "High valuation multiple leaves little room for error. Competition from larger players. Macro uncertainty.",
                "sector_outlook": "bullish"
            }
        
        elif "risk" in prompt.lower() or "pre-mortem" in prompt.lower():
            return {
                "failure_scenarios": [
                    {"scenario": "Technical breakdown below key support", "mitigation": "Set stop at -8%", "probability": "medium"},
                    {"scenario": "Earnings miss and guidance cut", "mitigation": "Reduce position before earnings", "probability": "low"},
                    {"scenario": "Sector rotation out of growth", "mitigation": "Diversify across sectors", "probability": "medium"}
                ],
                "risk_score": 0.45,
                "position_size_recommendation": "half",
                "stop_loss_level": 95.0
            }
        
        elif "technical" in prompt.lower():
            return {
                "support_levels": [95.0, 90.0, 85.0],
                "resistance_levels": [105.0, 110.0, 115.0],
                "ma_status": "neutral",
                "rsi_reading": 58.0,
                "rsi_interpretation": "neutral",
                "chart_pattern": "consolidation",
                "technical_outlook": "bullish",
                "key_observation": "Price holding above key support with rising volume"
            }
        
        elif "value" in prompt.lower():
            return {
                "has_moat": True,
                "moat_description": "Strong brand and network effects create high switching costs",
                "moat_strength": "moderate",
                "financial_health_score": 0.75,
                "financial_summary": "Growing revenue with improving margins. Strong balance sheet.",
                "valuation_vs_intrinsic": "fairly_valued",
                "margin_of_safety": 15.0,
                "margin_of_safety_explanation": "Trading near fair value with moderate margin of safety",
                "value_investor_rating": "buy"
            }
        
        elif "sentiment" in prompt.lower():
            return {
                "news_sentiment": "positive",
                "social_sentiment": "bullish",
                "crowd_psychology": "neutral",
                "sentiment_score": "greed",
                "contrarian_opportunity": False,
                "contrarian_explanation": "",
                "sentiment_summary": "Positive sentiment with moderate bullish bias. No extreme positioning."
            }
        
        else:  # geopolitical
            return {
                "exposed_risks": ["Trade policy uncertainty", "Regulatory scrutiny"],
                "risk_level": "medium",
                "risk_explanation": "Moderate exposure to geopolitical headwinds",
                "hedging_recommendations": ["Diversify internationally", "Monitor policy developments"]
            }
    
    def analyze_stock(self, ticker: str, stock_data: dict, social_data: dict, technical_data: dict) -> Dict:
        """
        Run complete multi-dimensional AI analysis.
        
        Args:
            ticker: Stock symbol
            stock_data: From data.market_data.get_stock_info()
            social_data: From data.social_signals.get_social_intelligence()
            technical_data: From data.technical_analysis.get_technical_analysis()
        
        Returns:
            Comprehensive analysis dict with scores and recommendations
        """
        
        print(f"  Running AI analysis for {ticker}...")
        
        # Build context for prompts
        context = build_prompt_context(ticker, stock_data, social_data, technical_data)
        
        # Run each enabled analysis
        results = {}
        
        if AI_CONFIG.enable_360_scanner:
            print(f"    → 360° Market Scanner...")
            prompt = PROMPT_360_SCANNER.format(**context)
            results['scanner'] = self._call_llm(prompt)
        
        if AI_CONFIG.enable_risk_assessment:
            print(f"    → Risk Assessment...")
            prompt = PROMPT_RISK_ASSESSMENT.format(**context)
            results['risk'] = self._call_llm(prompt)
        
        if AI_CONFIG.enable_technical_analysis:
            print(f"    → Technical Analysis...")
            prompt = PROMPT_TECHNICAL.format(**context)
            results['technical'] = self._call_llm(prompt)
        
        if AI_CONFIG.enable_value_analysis:
            print(f"    → Value Investor Analysis...")
            prompt = PROMPT_VALUE_INVESTOR.format(**context)
            results['value'] = self._call_llm(prompt)
        
        if AI_CONFIG.enable_sentiment_analysis:
            print(f"    → Sentiment Gauge...")
            prompt = PROMPT_SENTIMENT.format(**context)
            results['sentiment'] = self._call_llm(prompt)
        
        if AI_CONFIG.enable_geopolitical:
            print(f"    → Geopolitical Risk...")
            prompt = PROMPT_GEOPOLITICAL.format(**context)
            results['geopolitical'] = self._call_llm(prompt)
        
        # Synthesize results
        final_analysis = self._synthesize_results(ticker, results, context)
        
        print(f"  ✓ Analysis complete for {ticker}")
        
        return final_analysis
    
    def _synthesize_results(self, ticker: str, results: Dict, context: Dict) -> Dict:
        """
        Synthesize all analyses into final recommendation.
        
        Calculates composite scores and determines overall rating.
        """
        
        # Calculate component scores (1-5 scale)
        fundamental_score = self._score_fundamentals(results.get('scanner', {}), results.get('value', {}))
        technical_score = self._score_technical(results.get('technical', {}))
        sentiment_score = self._score_sentiment(results.get('sentiment', {}))
        
        # Risk score (0-1, where 1 = highest risk)
        risk_score = results.get('risk', {}).get('risk_score', 0.5)
        
        # Calculate risk-adjusted composite score
        # Weighted average with risk penalty
        raw_composite = (
            fundamental_score * AI_CONFIG.fundamental_weight +
            technical_score * AI_CONFIG.technical_weight +
            sentiment_score * AI_CONFIG.sentiment_weight
        )
        
        # Apply risk penalty (max 20% reduction)
        risk_penalty = risk_score * AI_CONFIG.risk_penalty_weight
        composite_score = raw_composite * (1 - risk_penalty)
        
        # Determine rating and conviction
        rating, conviction = self._determine_rating(
            composite_score, 
            fundamental_score,
            technical_score,
            sentiment_score,
            risk_score
        )
        
        # Determine hold period
        hold_period = self._determine_hold_period(technical_score, fundamental_score, risk_score)
        
        # Position sizing
        position_size = results.get('risk', {}).get('position_size_recommendation', 'half')
        stop_loss = results.get('risk', {}).get('stop_loss_level', context.get('price', 0) * 0.92)
        
        # Extract key insights
        bull_case = results.get('scanner', {}).get('bull_case', '')
        bear_case = results.get('scanner', {}).get('bear_case', '')
        key_risks = results.get('scanner', {}).get('major_headwinds', [])[:3]
        catalysts = results.get('scanner', {}).get('growth_drivers', [])[:3]
        
        # Check for contrarian opportunity
        is_contrarian = results.get('sentiment', {}).get('contrarian_opportunity', False)
        
        return {
            'ticker': ticker,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            
            # Composite scores
            'fundamental_score': round(float(fundamental_score), 2),
            'technical_score': round(float(technical_score), 2),
            'sentiment_score': round(float(sentiment_score), 2),
            'risk_score': round(float(risk_score), 2),
            'composite_score': round(float(composite_score), 2),
            
            # Final recommendation
            'rating': rating,
            'conviction': conviction,
            'hold_period': hold_period,
            'position_size': position_size,
            'stop_loss': round(float(stop_loss), 2),
            
            # Key insights
            'bull_case': bull_case,
            'bear_case': bear_case,
            'key_risks': key_risks,
            'catalysts': catalysts,
            'is_contrarian_opportunity': is_contrarian,
            
            # Raw analysis results
            'raw_results': results
        }
    
    def _score_fundamentals(self, scanner: Dict, value: Dict) -> float:
        """Score fundamentals 1-5 based on 360 scanner and value analysis."""
        score = 3.0  # Neutral baseline
        
        # Sector outlook
        outlook = scanner.get('sector_outlook', 'neutral')
        if outlook == 'bullish':
            score += 0.5
        elif outlook == 'bearish':
            score -= 0.5
        
        # Value investor rating
        value_rating = value.get('value_investor_rating', 'hold')
        if value_rating == 'strong_buy':
            score += 1.0
        elif value_rating == 'buy':
            score += 0.5
        elif value_rating == 'avoid':
            score -= 1.0
        
        # Moat presence
        if value.get('has_moat', False):
            moat_strength = value.get('moat_strength', 'weak')
            if moat_strength == 'strong':
                score += 0.5
            elif moat_strength == 'moderate':
                score += 0.3
        
        return max(1.0, min(5.0, score))
    
    def _score_technical(self, technical: Dict) -> float:
        """Score technicals 1-5."""
        score = 3.0
        
        outlook = technical.get('technical_outlook', 'neutral')
        if outlook == 'bullish':
            score += 1.0
        elif outlook == 'bearish':
            score -= 1.0
        
        # MA status
        ma_status = technical.get('ma_status', 'neutral')
        if ma_status == 'golden_cross':
            score += 0.5
        elif ma_status == 'death_cross':
            score -= 0.5
        
        # RSI
        rsi_interp = technical.get('rsi_interpretation', 'neutral')
        if rsi_interp == 'neutral':
            score += 0.5
        elif rsi_interp == 'overbought':
            score -= 0.3
        
        return max(1.0, min(5.0, score))
    
    def _score_sentiment(self, sentiment: Dict) -> float:
        """Score sentiment 1-5."""
        score = 3.0
        
        # Contrarian opportunity (highest value)
        if sentiment.get('contrarian_opportunity', False):
            return 4.5
        
        sentiment_level = sentiment.get('sentiment_score', 'neutral')
        if sentiment_level == 'extreme_greed':
            score -= 1.0
        elif sentiment_level == 'greed':
            score += 0.5
        elif sentiment_level == 'fear':
            score += 0.5
        elif sentiment_level == 'extreme_fear':
            score -= 0.5
        
        return max(1.0, min(5.0, score))
    
    def _determine_rating(self, composite: float, fundamental: float, 
                         technical: float, sentiment: float, risk: float) -> tuple:
        """Determine overall rating and conviction level."""
        
        if composite >= 4.5:
            rating = "STRONG_BUY"
            conviction = "HIGH"
        elif composite >= 3.5:
            rating = "BUY"
            conviction = "HIGH" if fundamental >= 4.0 else "MEDIUM"
        elif composite >= 3.0:
            rating = "HOLD"
            conviction = "MEDIUM"
        elif composite >= 2.5:
            rating = "WEAK_HOLD"
            conviction = "LOW"
        else:
            rating = "AVOID"
            conviction = "LOW"
        
        # Downgrade if high risk
        if risk > 0.7:
            if rating == "STRONG_BUY":
                rating = "BUY"
            conviction = "LOW"
        
        return rating, conviction
    
    def _determine_hold_period(self, technical: float, fundamental: float, risk: float) -> str:
        """Recommend hold period based on analysis."""
        
        # High risk = shorter hold
        if risk > 0.7:
            return "1-3 days (high risk, quick flip)"
        
        # Technical play
        if technical >= 4.0 and fundamental < 3.5:
            return "1-2 weeks (technical momentum)"
        
        # Value play
        if fundamental >= 4.0:
            return "1-3 months (value opportunity)"
        
        # Balanced
        return "2-4 weeks (swing trade)"


if __name__ == "__main__":
    # Test the analyzer
    print(f"\n{'='*60}")
    print("Testing AI Analyzer")
    print(f"{'='*60}\n")
    
    # Mock test data
    test_ticker = "PLTR"
    
    stock_data = {
        'price': 50.0,
        'market_cap': 100_000_000_000,
        'sector': 'Technology',
        'change_7d': 5.0,
        'change_1d': 1.0,
        'change_90d': 15.0,
        'pe_ratio': 25.0,
        'revenue_growth': 20.0,
        'profit_margin': 15.0,
        'float_millions': 100.0,
        'short_percent': 5.0
    }
    
    social_data = {
        'x_recent_mentions': 50,
        'reddit_total_mentions': 20,
        'is_accelerating': True,
        'catalyst_count': 2,
        'signal_strength': 'strong'
    }
    
    technical_data = {
        'rsi': 58.0,
        'volume_analysis': {'volume_ratio': 1.5},
        'moving_averages': {'sma_20': 48.0, 'sma_50': 45.0},
        'technical_outlook': 'bullish'
    }
    
    analyzer = AIAnalyzer()
    result = analyzer.analyze_stock(test_ticker, stock_data, social_data, technical_data)
    
    print(f"\nResults for {test_ticker}:")
    print(f"  Rating: {result['rating']}")
    print(f"  Conviction: {result['conviction']}")
    print(f"  Composite Score: {result['composite_score']}/5.0")
    print(f"  Hold Period: {result['hold_period']}")
    print(f"  Position Size: {result['position_size']}")
    print(f"  Stop Loss: ${result['stop_loss']:.2f}")
    print(f"\n  Component Scores:")
    print(f"    Fundamental: {result['fundamental_score']}/5.0")
    print(f"    Technical: {result['technical_score']}/5.0")
    print(f"    Sentiment: {result['sentiment_score']}/5.0")
    print(f"    Risk: {result['risk_score']}/1.0")