"""
run_execution_v1.py — Supabot V3 Live Execution Runner

Runs today's scan and feeds picks directly into the live Alpaca execution
layer.  Does NOT read alpaca_positions.json; candidates come from the scan.

Dollar sizing by V4 score:
    120–129  →  $80 notional
    130+     →  $60 notional

Called by the 3:30 PM ET GitHub Actions workflow.
"""

from supabot_v3 import scan
from alpaca_execution_v1 import run_execution


def score_to_notional(score: float) -> float:
    """Map V4 score tier to position size in dollars."""
    if score >= 130:
        return 60.0
    return 80.0  # 120–129


def build_candidates(picks: list) -> list[dict]:
    """
    Convert supabot_v3 scan picks to execution candidate dicts.

    - Filters out picks with v4_score < 120
    - Maps ticker → symbol, v4_score → score
    - Applies notional sizing by score tier
    - Sorts descending by score
    """
    candidates = []
    for pick in picks:
        score = float(pick.get("v4_score", 0))
        if score < 120:
            continue
        candidates.append({
            "symbol":                  pick["ticker"],
            "score":                   score,
            "target_notional_dollars": score_to_notional(score),
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Supabot V3 — Live Execution Runner")
    print("=" * 60)

    print("\n[1/2] Running scan ...")
    picks, _ = scan()
    print(f"  Scan returned {len(picks)} pick(s)")

    candidates = build_candidates(picks)
    print(f"  Candidates with score >= 120: {len(candidates)}")
    for c in candidates:
        print(f"    {c['symbol']:6s}  score={c['score']:.0f}  notional=${c['target_notional_dollars']:.0f}")

    print("\n[2/2] Running live execution ...")
    # Always call run_execution — even with empty candidates — so due sells still happen.
    run_execution(candidates)
