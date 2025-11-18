"""
Supabot V2 - Discord Notifications (UPDATED)
Added mention counts to Discord notifications
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

from config import DISCORD_WEBHOOK_URL, DISPLAY_CONFIG

def send_scan_results(df: pd.DataFrame, scan_stats: dict = None):
    """
    Send scan results to Discord with mention counts.
    """
    
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  Discord webhook not configured. Skipping notification.")
        return
    
    if not DISPLAY_CONFIG.send_to_discord:
        print("Discord notifications disabled in config")
        return
    
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, username="Supabot V2")
    
    # No candidates found
    if df.empty:
        embed = DiscordEmbed(
            title="📊 Supabot V2 Scan Complete",
            description="No high-quality candidates found this scan.\nMarket is quiet or filters are strict.",
            color='808080'
        )
        embed.set_footer(text=f"Scan: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        webhook.add_embed(embed)
        
        try:
            webhook.execute()
            print("✅ Discord notification sent (no candidates)")
        except Exception as e:
            print(f"⚠️  Discord error: {e}")
        
        return
    
    # Build title with stats
    fresh_count = len(df[df.get('is_fresh', False) == True])
    high_conviction = len(df[df.get('conviction', '') == 'HIGH'])
    
    title = f"🎯 {len(df)} Quality Candidates Found"
    if fresh_count > 0:
        title += f" | ✨ {fresh_count} Fresh"
    if high_conviction > 0:
        title += f" | 🔥 {high_conviction} High Conviction"
    
    # Main embed
    embed = DiscordEmbed(
        title=title,
        description=f"Scanned {scan_stats.get('scanned', 0) if scan_stats else '?'} stocks, found {len(df)} high-quality setups",
        color='03b2f8'
    )
    
    # Add top candidates
    for i, (_, row) in enumerate(df.head(5).iterrows(), 1):
        # Build signals
        signals = []
        if row.get('is_fresh'):
            signals.append("✨")
        if row.get('is_accelerating'):
            signals.append("📈")
        if row.get('has_catalysts'):
            signals.append("📰")
        if row.get('parabolic_setup'):
            signals.append("💥")
        if row.get('squeeze_potential'):
            signals.append("🚀")
        
        signal_str = " ".join(signals) if signals else "—"
        
        # Build field
        rating = row.get('rating', 'HOLD')
        conviction = row.get('conviction', 'MEDIUM')
        conviction_emoji = "🔥" if conviction == 'HIGH' else "⚡" if conviction == 'MEDIUM' else ""
        
        name = f"#{i}. {row['ticker']} {signal_str}"
        
        # BUILD VALUE WITH MENTIONS ← UPDATED!
        value_parts = [
            f"**{rating}** {conviction_emoji}",
            f"Score: {row.get('composite_score', 0):.2f}/5.0",
            f"Price: ${row.get('price', 0):.2f}",
            f"7d: {row.get('change_7d', 0):+.1f}%",
        ]
        
        # ADD MENTIONS ← NEW!
        twitter = row.get('x_mentions', 0)
        reddit = row.get('reddit_total_mentions', 0)  # Try multiple column names
        if twitter == 0:
            twitter = row.get('twitter_mentions', 0)
        if reddit == 0:
            reddit = row.get('reddit_mentions', 0)
        
        if twitter > 0 or reddit > 0:
            value_parts.append(f"Buzz: {twitter}🐦 {reddit}🤖")
        
        # Add notable info
        if row.get('has_catalysts'):
            value_parts.append(f"Catalysts: {row.get('catalyst_count', 0)}")
        
        if row.get('short_percent', 0) > 15:
            value_parts.append(f"Short: {row.get('short_percent', 0):.0f}%")
        
        embed.add_embed_field(
            name=name,
            value=" | ".join(value_parts),
            inline=False
        )
    
    # Add risk management summary
    if not df.empty:
        top_pick = df.iloc[0]
        embed.add_embed_field(
            name="🛡️ Risk Management (Top Pick)",
            value=f"**{top_pick['ticker']}:** {top_pick.get('position_size', 'unknown')} position | Stop: ${top_pick.get('stop_loss', 0):.2f} | Hold: {top_pick.get('hold_period', 'unknown')}",
            inline=False
        )
    
    # Footer
    embed.set_footer(text=f"Supabot V2 | {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    
    webhook.add_embed(embed)
    
    try:
        webhook.execute()
        print(f"✅ Discord notification sent ({len(df)} candidates)")
    except Exception as e:
        print(f"⚠️  Discord notification failed: {e}")


def send_high_conviction_alert(row: pd.Series):
    """
    Send special alert for high-conviction plays with mentions.
    """
    
    if not DISCORD_WEBHOOK_URL or not DISPLAY_CONFIG.send_jackpot_alerts:
        return
    
    ticker = row['ticker']
    
    # Only send for HIGH conviction + STRONG_BUY or BUY
    if row.get('conviction') != 'HIGH':
        return
    
    if row.get('rating') not in ['STRONG_BUY', 'BUY']:
        return
    
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, username="Supabot V2 ALERT")
    
    # Check if it's a jackpot (fresh + accelerating + catalysts)
    is_jackpot = (
        row.get('is_fresh', False) and
        row.get('is_accelerating', False) and
        row.get('has_catalysts', False)
    )
    
    if is_jackpot:
        embed = DiscordEmbed(
            title=f"🔥 JACKPOT ALERT: {ticker}",
            description="Fresh + Accelerating + Catalysts = RARE SETUP!",
            color='ff0000'
        )
    else:
        embed = DiscordEmbed(
            title=f"⚡ HIGH CONVICTION: {ticker}",
            description=f"{row['rating']} with HIGH conviction",
            color='00ff00'
        )
    
    # Add details
    embed.add_embed_field(name="Price", value=f"${row['price']:.2f}", inline=True)
    embed.add_embed_field(name="Score", value=f"{row['composite_score']:.2f}/5.0", inline=True)
    embed.add_embed_field(name="7d Change", value=f"{row['change_7d']:+.1f}%", inline=True)
    
    embed.add_embed_field(name="Position Size", value=row.get('position_size', 'unknown'), inline=True)
    embed.add_embed_field(name="Stop Loss", value=f"${row['stop_loss']:.2f}", inline=True)
    embed.add_embed_field(name="Hold Period", value=row.get('hold_period', 'unknown'), inline=True)
    
    # ADD MENTIONS ← NEW!
    twitter = row.get('x_mentions', row.get('twitter_mentions', 0))
    reddit = row.get('reddit_total_mentions', row.get('reddit_mentions', 0))
    
    if twitter > 0 or reddit > 0:
        embed.add_embed_field(
            name="Social Buzz",
            value=f"{twitter}🐦 Twitter | {reddit}🤖 Reddit",
            inline=False
        )
    
    # Signals
    signals = []
    if row.get('is_fresh'): signals.append("✨ Fresh")
    if row.get('is_accelerating'): signals.append("📈 Accelerating")
    if row.get('has_catalysts'): signals.append(f"📰 {row.get('catalyst_count', 0)} Catalysts")
    if row.get('parabolic_setup'): signals.append("💥 Parabolic")
    if row.get('squeeze_potential'): signals.append("🚀 Squeeze")
    
    if signals:
        embed.add_embed_field(
            name="Special Signals",
            value="\n".join(signals),
            inline=False
        )
    
    embed.set_footer(text="⚠️ High conviction play - review carefully!")
    
    webhook.add_embed(embed)
    
    try:
        webhook.execute()
        print(f"🚨 High conviction alert sent for {ticker}!")
    except Exception as e:
        print(f"⚠️  Alert failed: {e}")


if __name__ == "__main__":
    # Test notifications
    print("\nTesting Discord Notifications...\n")
    
    # Test with sample data
    test_data = pd.DataFrame([{
        'ticker': 'TEST',
        'price': 50.0,
        'rating': 'BUY',
        'conviction': 'HIGH',
        'composite_score': 4.2,
        'change_7d': 5.5,
        'is_fresh': True,
        'is_accelerating': True,
        'has_catalysts': True,
        'catalyst_count': 2,
        'x_mentions': 35,
        'reddit_mentions': 5,
        'position_size': 'half',
        'stop_loss': 46.0,
        'hold_period': '2-4 weeks'
    }])
    
    send_scan_results(test_data, {'scanned': 100})
    send_high_conviction_alert(test_data.iloc[0])
    
    print("\n✓ Test complete! Check Discord.")