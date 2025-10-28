"""
Supabot V2 - AI Master Prompts
6 expert-level prompts for multi-dimensional stock analysis.
"""

# ============ Prompt 1: 360° Market Scanner ============

PROMPT_360_SCANNER = """Act as a senior market analyst for a hedge fund. Analyze {ticker} ({company_name}) in the context of its sector: {sector}.

**FINANCIAL METRICS (Latest Quarter):**
- Revenue: ${revenue:.0f}M (Growth: {revenue_growth:+.1f}%)
- Gross Margin: {gross_margin:.1f}%
- Operating Margin: {operating_margin:.1f}%  
- FCF Margin: {fcf_margin:.1f}%
- Debt/Equity: {debt_to_equity_ratio:.2f}

**VALUATION:**
- Market Cap: ${market_cap_billions:.2f}B
- EV/EBITDA: {ev_to_ebitda:.1f}x
- Price/FCF: {price_to_fcf:.1f}x
- FCF Yield: {fcf_yield:.2f}%
- P/E: {pe_ratio:.1f}

**RECENT CATALYSTS:**
- News Sentiment: {news_sentiment} ({positive_news_count} positive articles)
- Catalyst Summary: {catalyst_summary}
- Next Earnings: {earnings_date} ({days_until_earnings} days)

**PRICE ACTION:**
- Current: ${price:.2f}
- 7-day: {change_7d:+.1f}%
- 90-day: {change_90d:+.1f}%

**CRITICAL:** With these fundamentals and catalysts, assess if this is a quality investment opportunity or a value trap.

**CRITICAL CONTEXT:**
- Current Price: ${price:.2f}
- Market Cap: ${market_cap_billions:.2f}B
- 7-Day Change: {change_7d:+.1f}%
- 1-Day Change: {change_1d:+.1f}%
- Social Buzz: {social_signal}

**If this stock is up >20% in 7 days or >12% in 1 day, you are analyzing LATE-STAGE momentum. The easy money has been made. Be conservative in your scoring and flag the entry risk.**

Your analysis must include:

1. **Key Growth Drivers:** What are the top 3 secular trends powering this company? Be specific.

2. **Major Headwinds:** What are the most significant risks or challenges facing the company? List 3.

3. **Competitive Position:** Does {ticker} have a durable competitive advantage (moat)? Describe it concisely.

4. **Recent Catalysts:** Based on the context provided, what recent events or catalysts might be driving interest?

5. **Bull & Bear Case:** 
   - Bull case: Why the stock could outperform in next 6 months (3 sentences)
   - Bear case: Why the stock could underperform (3 sentences)

6. **Sector Outlook:** Is the sector outlook bullish, bearish, or neutral?

OUTPUT FORMAT (JSON ONLY):
{{
  "growth_drivers": ["driver1", "driver2", "driver3"],
  "major_headwinds": ["risk1", "risk2", "risk3"],
  "competitive_position": "description of moat (2-3 sentences)",
  "recent_catalysts": "description (1-2 sentences)",
  "bull_case": "why outperform (3 sentences)",
  "bear_case": "why underperform (3 sentences)",
  "sector_outlook": "bullish|bearish|neutral"
}}

Respond ONLY with valid JSON. Be concise but specific."""

# ============ Prompt 2: Pre-mortem Risk Assessment ============

PROMPT_RISK_ASSESSMENT = """Act as a risk management expert. I am considering trading {ticker} at ${price:.2f}.

**Current Context:**
- 7-day momentum: {change_7d:+.1f}%
- Float: {float_millions:.1f}M shares
- Short interest: {short_percent:.1f}%
- Social buzz: {social_signal}
- Technical setup: {technical_outlook}

Conduct a "pre-mortem" analysis. Assume that in 3 months, this trade resulted in a -20%+ loss.

Describe the three most likely scenarios that led to failure:

1. **Technical Failure:** Chart breakdown, key support level broken, or momentum reversal
2. **Fundamental Failure:** Earnings miss, guidance cut, sector weakness, or competitive pressure
3. **External Shock:** Macro event, regulatory issue, or black swan event

For EACH scenario, suggest:
- Specific mitigation strategy (e.g., "Set stop-loss at $X", "Hedge with puts at Y strike")
- Probability: low, medium, or high

Then provide:
- Overall risk score (0.0 = low risk, 1.0 = extreme risk)
- Position size recommendation: "full" (10%), "half" (5%), "quarter" (2.5%), or "avoid"
- Suggested stop-loss level (dollar amount)

**Consider these risk factors:**
- Already up {change_7d:+.1f}% in 7 days (chase risk)
- Float size (small float = higher volatility)
- Short interest (squeeze potential vs. bearish signal)

OUTPUT FORMAT (JSON ONLY):
{{
  "failure_scenarios": [
    {{"scenario": "technical failure description", "mitigation": "specific strategy", "probability": "low|medium|high"}},
    {{"scenario": "fundamental failure description", "mitigation": "specific strategy", "probability": "low|medium|high"}},
    {{"scenario": "external shock description", "mitigation": "specific strategy", "probability": "low|medium|high"}}
  ],
  "risk_score": 0.0-1.0,
  "position_size_recommendation": "full|half|quarter|avoid",
  "stop_loss_level": dollar_amount
}}

Respond ONLY with valid JSON."""

# ============ Prompt 3: Multi-Timeframe Technical Analysis ============

PROMPT_TECHNICAL = """Act as a Chartered Market Technician (CMT). Provide detailed technical analysis for {ticker}.

**Current Data:**
- Price: ${price:.2f}
- 7-day change: {change_7d:+.1f}%
- RSI: {rsi:.1f}
- Volume ratio: {volume_ratio:.2f}x average
- Moving averages: SMA20=${sma_20:.2f}, SMA50=${sma_50:.2f}

Your analysis must be structured as follows:

1. **Key Levels:** Identify the primary support levels (3) and resistance levels (3) based on recent price action.

2. **Moving Averages:** Analyze the 20-day and 50-day moving averages. Is there a "golden cross" (bullish) or "death cross" (bearish) present or approaching?

3. **RSI Analysis:** Current RSI is {rsi:.1f}. Is the stock overbought (>70), oversold (<30), or neutral (30-70)?

4. **Chart Patterns:** Based on the price action, are there any recognizable chart patterns forming? (e.g., bull flag, ascending triangle, head and shoulders, cup and handle, consolidation)

5. **Technical Outlook:** Based ONLY on the technical factors above, is the outlook bullish, bearish, or neutral?

OUTPUT FORMAT (JSON ONLY):
{{
  "support_levels": [level1, level2, level3],
  "resistance_levels": [level1, level2, level3],
  "ma_status": "golden_cross|death_cross|neutral",
  "rsi_reading": {rsi:.1f},
  "rsi_interpretation": "overbought|oversold|neutral",
  "chart_pattern": "pattern name or 'none'",
  "technical_outlook": "bullish|bearish|neutral",
  "key_observation": "1-2 sentence summary"
}}

Respond ONLY with valid JSON."""

# ============ Prompt 4: Value Investor Analysis ============

PROMPT_VALUE_INVESTOR = """Act as a value investor in the Benjamin Graham / Warren Buffett tradition. Evaluate {ticker} for long-term investment.

**Company Data:**
- Price: ${price:.2f}
- Market Cap: ${market_cap_billions:.2f}B
- P/E Ratio: {pe_ratio:.1f}
- Revenue Growth: {revenue_growth:+.1f}%
- Profit Margin: {profit_margin:.1f}%
- Recent performance: {change_7d:+.1f}% (7d), {change_90d:+.1f}% (90d)

Evaluate based on value investing principles:

1. **Business Quality:** Does the company have a durable competitive advantage (economic moat)? Consider:
   - Brand strength
   - Network effects
   - Cost advantages
   - Switching costs
   - Regulatory barriers

2. **Financial Health:** Briefly analyze:
   - Revenue growth trend
   - Profit margins (expanding or contracting?)
   - Free cash flow generation
   - Balance sheet strength

3. **Valuation:** Based on its P/E ratio of {pe_ratio:.1f}:
   - How does it compare to historical averages?
   - How does it compare to competitors in {sector}?
   - Is it trading at a reasonable price relative to growth?

4. **Margin of Safety:** Is the stock currently trading at a price that offers a significant "margin of safety" below your estimate of its intrinsic value?

**Important:** If the stock is up {change_7d:+.1f}% in 7 days, it may not offer a good margin of safety regardless of quality.

OUTPUT FORMAT (JSON ONLY):
{{
  "has_moat": true|false,
  "moat_description": "description of competitive advantage (2-3 sentences)",
  "moat_strength": "strong|moderate|weak",
  "financial_health_score": 0.0-1.0,
  "financial_summary": "brief assessment (2 sentences)",
  "valuation_vs_intrinsic": "undervalued|fairly_valued|overvalued",
  "margin_of_safety": percentage_as_number,
  "margin_of_safety_explanation": "brief explanation (1-2 sentences)",
  "value_investor_rating": "strong_buy|buy|hold|avoid"
}}

Respond ONLY with valid JSON."""

# ============ Prompt 5: Market Sentiment Gauge ============

PROMPT_SENTIMENT = """Act as a behavioral finance expert. Analyze market sentiment for {ticker}.

**Current Context:**
- X/Twitter mentions: {x_mentions}
- Reddit quality mentions: {reddit_mentions}
- Social acceleration: ACCELERATING={is_accelerating}
- Catalysts detected: {catalyst_count}
- Price action: {change_7d:+.1f}% (7d)
- Volatility: {volatility_description}

Use a multi-factor approach:

1. **News Sentiment:** Based on social activity and price action, what is the general tone? (Positive, negative, neutral)

2. **Social Media:** What is the prevailing sentiment on X/Twitter and Reddit? (Bullish, neutral, bearish)

3. **Crowd Psychology:** Based on the price action ({change_7d:+.1f}% in 7d), are we seeing:
   - FOMO (Fear of Missing Out) - everyone rushing in
   - Fear - panic selling
   - Neutral - rational price action

4. **Contrarian Analysis:** Look for contrarian opportunities:
   - Extreme fear + solid fundamentals = BUY signal
   - Extreme greed + weak fundamentals = AVOID

5. **Sentiment Score:** Rate overall sentiment on this scale:
   - "extreme_fear" - Maximum pessimism (contrarian buy opportunity)
   - "fear" - Selling pressure
   - "neutral" - Balanced
   - "greed" - Buying pressure
   - "extreme_greed" - Maximum optimism (contrarian sell signal)

**Key Question:** Is this a contrarian opportunity? (Fear + quality = YES)

OUTPUT FORMAT (JSON ONLY):
{{
  "news_sentiment": "positive|neutral|negative",
  "social_sentiment": "bullish|neutral|bearish",
  "crowd_psychology": "FOMO|fear|neutral",
  "sentiment_score": "extreme_fear|fear|neutral|greed|extreme_greed",
  "contrarian_opportunity": true|false,
  "contrarian_explanation": "explanation if true (2 sentences)",
  "sentiment_summary": "brief summary (2-3 sentences)"
}}

Respond ONLY with valid JSON."""

# ============ Prompt 6: Geopolitical Risk Assessment ============

PROMPT_GEOPOLITICAL = """Act as a geopolitical strategist. Assess {ticker}'s exposure to current global risks.

**Company Context:**
- Sector: {sector}
- Market Cap: ${market_cap_billions:.2f}B
- International operations: {has_international}

Consider current geopolitical landscape and assess exposure to:

1. **Trade Tensions:** US-China relations, tariffs, export controls
2. **Regional Conflicts:** Geopolitical instability in key markets
3. **Regulatory Risks:** Sector-specific regulations, antitrust, data privacy
4. **Supply Chain:** Vulnerabilities to disruption
5. **Currency Risk:** Exposure to foreign exchange fluctuations

For this specific company in the {sector} sector:
- Which 2 specific geopolitical risks are most relevant?
- What is the overall risk level: low, medium, or high?
- What hedging strategies could mitigate these risks?

OUTPUT FORMAT (JSON ONLY):
{{
  "exposed_risks": ["risk1", "risk2"],
  "risk_level": "low|medium|high",
  "risk_explanation": "brief explanation (2-3 sentences)",
  "hedging_recommendations": ["strategy1", "strategy2"]
}}

Respond ONLY with valid JSON. If geopolitical risks are minimal for this company, state that clearly."""


# ============ Prompt Context Builder ============

def build_prompt_context(ticker: str, stock_data: dict, social_data: dict, technical_data: dict) -> dict:
    """
    Build context dictionary for prompt templates with ENHANCED data.
    
    Args:
        ticker: Stock symbol
        stock_data: From get_stock_info()
        social_data: From get_social_intelligence()
        technical_data: From get_technical_analysis()
    
    Returns:
        Dict with all variables needed for AI prompt formatting
    """
    
    # Import enhanced data modules
    try:
        from data.fundamentals import get_financial_statements, calculate_advanced_valuation, calculate_quality_score
        from data.news_events import get_catalyst_summary
        
        # Get enhanced fundamental data
        financials = get_financial_statements(ticker)
        valuation = calculate_advanced_valuation(ticker)
        catalysts = get_catalyst_summary(ticker)
        quality_score = calculate_quality_score(financials)
    except Exception as e:
        print(f"Warning: Could not load enhanced data for {ticker}: {e}")
        financials = {}
        valuation = {}
        catalysts = {}
        quality_score = 0.5
    
    # Extract price changes (ensure they exist in stock_data)
    change_7d = stock_data.get('change_7d', 0)
    change_1d = stock_data.get('change_1d', 0)
    change_90d = stock_data.get('change_90d', 0)
    
    # Extract and format basic data
    price = stock_data.get('price', 0)
    market_cap = stock_data.get('market_cap', 0)
    
    # Extract social data safely
    x_mentions = social_data.get('x_recent_mentions', 0)
    reddit_mentions = social_data.get('reddit_total_mentions', 0)
    is_accelerating = social_data.get('is_accelerating', False)
    catalyst_count = social_data.get('catalyst_count', 0)
    
    # Extract technical data safely
    rsi = technical_data.get('rsi', 50)
    volume_analysis = technical_data.get('volume_analysis', {})
    volume_ratio = volume_analysis.get('volume_ratio', 1.0)
    moving_averages = technical_data.get('moving_averages', {})
    sma_20 = moving_averages.get('sma_20', price)
    sma_50 = moving_averages.get('sma_50', price)
    
    # Build comprehensive context
    context = {
        # ============ Basic Info ============
        'ticker': ticker,
        'company_name': ticker,
        'price': float(price),
        'market_cap_billions': float(market_cap / 1_000_000_000) if market_cap > 0 else 0,
        'sector': stock_data.get('sector', 'Unknown'),
        'industry': stock_data.get('industry', 'Unknown'),
        
        # ============ Price Changes ============
        'change_7d': float(change_7d),
        'change_1d': float(change_1d),
        'change_90d': float(change_90d),
        
        # ============ Basic Fundamentals ============
        'pe_ratio': float(stock_data.get('pe_ratio', 0)),
        'forward_pe': float(stock_data.get('forward_pe', 0)),
        'peg_ratio': float(stock_data.get('peg_ratio', 0)),
        'revenue_growth': float(stock_data.get('revenue_growth', 0)),
        'profit_margin': float(stock_data.get('profit_margin', 0)),
        
        # ============ ENHANCED: Financial Statements ============
        'revenue': float(financials.get('revenue', 0) / 1_000_000),  # In millions
        'net_income': float(financials.get('net_income', 0) / 1_000_000),
        'free_cash_flow': float(financials.get('free_cash_flow', 0) / 1_000_000),
        'gross_margin': float(financials.get('gross_margin', 0)),
        'operating_margin': float(financials.get('operating_margin', 0)),
        'fcf_margin': float(financials.get('fcf_margin', 0)),
        'debt_to_equity_ratio': float(financials.get('debt_to_equity', 0)),
        'cash': float(financials.get('cash', 0) / 1_000_000),
        
        # ============ ENHANCED: Advanced Valuation ============
        'enterprise_value': float(valuation.get('enterprise_value', 0) / 1_000_000_000),  # In billions
        'ev_to_ebitda': float(valuation.get('ev_to_ebitda', 0)),
        'price_to_fcf': float(valuation.get('price_to_fcf', 0)),
        'fcf_yield': float(valuation.get('fcf_yield', 0)),
        'ev_to_revenue': float(valuation.get('ev_to_revenue', 0)),
        
        # ============ ENHANCED: Quality Score ============
        'fundamental_quality_score': float(quality_score),
        'quality_rating': 'high' if quality_score > 0.7 else 'medium' if quality_score > 0.4 else 'low',
        
        # ============ ENHANCED: Catalysts & News ============
        'catalyst_score': float(catalysts.get('catalyst_score', 0)),
        'catalyst_summary': str(catalysts.get('catalyst_summary', 'No recent catalysts')),
        'catalyst_types': catalysts.get('catalyst_types', []),
        'news_sentiment': str(catalysts.get('recent_news_sentiment', 'neutral')),
        'positive_news_count': int(catalysts.get('positive_news_count', 0)),
        'negative_news_count': int(catalysts.get('negative_news_count', 0)),
        
        # Earnings
        'earnings_date': str(catalysts.get('upcoming_earnings', {}).get('earnings_date', 'Unknown')),
        'days_until_earnings': int(catalysts.get('upcoming_earnings', {}).get('days_until_earnings', 999)),
        'is_earnings_week': bool(catalysts.get('upcoming_earnings', {}).get('is_earnings_week', False)),
        
        # ============ Float & Short ============
        'float_millions': float(stock_data.get('float_millions', 0)),
        'short_percent': float(stock_data.get('short_percent', 0)),
        
        # ============ Social Signals ============
        'x_mentions': int(x_mentions),
        'reddit_mentions': int(reddit_mentions),
        'is_accelerating': bool(is_accelerating),
        'social_acceleration': 'ACCELERATING' if is_accelerating else 'STABLE',
        'catalyst_count': int(catalyst_count),
        'social_signal': str(social_data.get('signal_strength', 'weak')),
        
        # ============ Technical ============
        'rsi': float(rsi),
        'volume_ratio': float(volume_ratio),
        'sma_20': float(sma_20),
        'sma_50': float(sma_50),
        'technical_outlook': str(technical_data.get('technical_outlook', 'neutral')),
        
        # ============ Volatility ============
        'volatility_description': 'high' if abs(change_7d) > 15 else 'moderate' if abs(change_7d) > 7 else 'low',
        
        # ============ International ============
        'has_international': 'Yes' if market_cap > 5_000_000_000 else 'Limited',
    }
    
    return context


if __name__ == "__main__":
    # Test prompt context builder
    print("AI Prompts Module Loaded Successfully!")
    print("\nAvailable Prompts:")
    print("  1. PROMPT_360_SCANNER")
    print("  2. PROMPT_RISK_ASSESSMENT")
    print("  3. PROMPT_TECHNICAL")
    print("  4. PROMPT_VALUE_INVESTOR")
    print("  5. PROMPT_SENTIMENT")
    print("  6. PROMPT_GEOPOLITICAL")
    print("\nUse build_prompt_context() to prepare data for these prompts.")