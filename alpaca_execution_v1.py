"""
alpaca_execution_v1.py — Supabot V3 Alpaca Execution Layer
===========================================================

Rock-solid buy/sell executor with idempotency, restart-safety, and exact
7-calendar-day hold timing.  Sells are always processed before buys.

Dependency note:
    This module requires the *alpaca-py* SDK (package name: alpaca-py), not the
    legacy alpaca-trade-api package already in requirements.txt.  Install once:

        pip install alpaca-py

    The two packages coexist safely; they have different top-level import names.

Caller interface::

    from alpaca_execution_v1 import run_execution

    run_execution(candidates=[
        {"symbol": "AAPL", "score": 145, "target_notional_dollars": 500},
        ...
    ])

Environment variables (required):
    APCA_API_KEY_ID       – Alpaca API key ID
    APCA_API_SECRET_KEY   – Alpaca API secret key
    APCA_PAPER            – "true" (default) for paper trading, "false" for live

State file:
    supabot_positions_state.json  (repo root, auto-created)
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetCalendarRequest,
    GetOrdersRequest,
    MarketOrderRequest,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILE = Path(__file__).parent / "supabot_positions_state.json"
ET = ZoneInfo("America/New_York")

MIN_SCORE: int = 120           # Minimum V4 score to consider a candidate
MAX_OPEN_POSITIONS: int = 12   # Hard cap on concurrent open positions
MAX_NEW_BUYS_PER_DAY: int = 2  # Max new positions opened per calendar day
HOLD_DAYS: int = 7             # Calendar days between entry and target exit

# Entry window: 15:25–15:40 ET
_ENTRY_START = (15, 25)
_ENTRY_END   = (15, 40)

# Exit window for same-day scheduled exits: 15:20–15:55 ET
_EXIT_START = (15, 20)
_EXIT_END   = (15, 55)

_POLL_INTERVAL_S = 5    # seconds between position-closed polls
_POLL_TIMEOUT_S  = 120  # max seconds to wait for position to confirm closed

_ACTIVE_STATUSES = {"open", "pending_exit", "imported_unknown_timing"}


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """
    Load execution state from disk.  Returns an empty structure if file absent.

    State schema::

        {
          "positions": {
            "AAPL": {
              "symbol":                "AAPL",
              "entry_time_et":         "2026-03-20T15:30:00-04:00",
              "exit_time_et":          "2026-03-27T15:30:00-04:00",
              "notional":              500.0,
              "score":                 145.0,
              "entry_client_order_id": "SBV3-ENTRY-20260320-AAPL",
              "entry_order_id":        "uuid...",
              "exit_client_order_id":  "SBV3-EXIT-20260327-AAPL",
              "exit_order_id":         null,
              "status":                "open"
            }
          },
          "daily_buys": {
            "2026-03-20": ["AAPL", "MSFT"]
          }
        }

    Position statuses:
        open                   – position is live, exit not yet due
        pending_exit           – sell was attempted (or is overdue); retry on next run
        closed                 – position fully exited
        imported_unknown_timing – Alpaca holds it but state had no record; best-effort timing
    """
    if STATE_FILE.exists():
        with STATE_FILE.open() as fh:
            data = json.load(fh)
        data.setdefault("positions", {})
        data.setdefault("daily_buys", {})
        return data
    return {"positions": {}, "daily_buys": {}}


def save_state(state: dict) -> None:
    """Persist state to disk via temp-file rename (atomic on POSIX)."""
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w") as fh:
        json.dump(state, fh, indent=2, default=str)
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def get_now_et(now: datetime | None = None) -> datetime:
    """Return the current datetime in US/Eastern, or convert *now* to ET."""
    if now is not None:
        return now.astimezone(ET)
    return datetime.now(tz=ET)


def _in_window(now_et: datetime, start: tuple[int, int], end: tuple[int, int]) -> bool:
    t = now_et.hour * 60 + now_et.minute
    return (start[0] * 60 + start[1]) <= t <= (end[0] * 60 + end[1])


def is_in_entry_window(now_et: datetime) -> bool:
    """Return True if *now_et* falls within the buy entry window (15:25–15:40 ET)."""
    return _in_window(now_et, _ENTRY_START, _ENTRY_END)


def is_in_exit_window(now_et: datetime) -> bool:
    """Return True if *now_et* falls within the sell exit window (15:20–15:55 ET)."""
    return _in_window(now_et, _EXIT_START, _EXIT_END)


# ---------------------------------------------------------------------------
# Alpaca client factory
# ---------------------------------------------------------------------------

def _make_client() -> TradingClient:
    key    = os.environ["APCA_API_KEY_ID"]
    secret = os.environ["APCA_API_SECRET_KEY"]
    paper  = _is_paper()
    return TradingClient(key, secret, paper=paper)


def _is_paper() -> bool:
    return os.environ.get("APCA_PAPER", "true").strip().lower() not in ("false", "0", "no")


# ---------------------------------------------------------------------------
# Market-hours helpers
# ---------------------------------------------------------------------------

def is_market_open(trading_client: TradingClient) -> bool:
    """Return True if the US equity market is currently open for trading."""
    return trading_client.get_clock().is_open


def _get_trading_dates(
    trading_client: TradingClient, start: date, end: date
) -> list[date]:
    """Return sorted list of market-open dates in [start, end] (inclusive)."""
    cal = trading_client.get_calendar(
        GetCalendarRequest(start=start.isoformat(), end=end.isoformat())
    )
    return sorted(c.date for c in cal)


def next_trading_day_at_1530(et_dt: datetime, trading_client: TradingClient) -> datetime:
    """
    Return a tz-aware datetime at 15:30 ET on the first trading day >= *et_dt*.date().

    If *et_dt*.date() is itself a trading day, returns that same date at 15:30 ET.
    Searches up to 14 calendar days forward to handle extended holiday breaks.

    Args:
        et_dt:          Reference datetime in ET (or any tz — will use .date()).
        trading_client: Authenticated TradingClient for calendar lookup.

    Returns:
        datetime at 15:30 ET on the first eligible trading day.

    Raises:
        RuntimeError: If no trading day is found in the look-ahead window.
    """
    start = et_dt.date()
    end   = start + timedelta(days=14)
    dates = _get_trading_dates(trading_client, start, end)
    if not dates:
        raise RuntimeError(f"No trading day found between {start} and {end}")
    first = dates[0]
    return datetime(first.year, first.month, first.day, 15, 30, 0, tzinfo=ET)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_exit_time(entry_et: datetime, trading_client: TradingClient) -> datetime:
    """
    entry_et + HOLD_DAYS calendar days, then snapped to next trading day at 15:30 ET.
    """
    raw = (entry_et + timedelta(days=HOLD_DAYS)).replace(
        hour=15, minute=30, second=0, microsecond=0
    )
    return next_trading_day_at_1530(raw, trading_client)


def _exit_time(rec: dict) -> datetime:
    """Parse the exit_time_et field, ensuring timezone info is set."""
    dt = datetime.fromisoformat(rec["exit_time_et"])
    return dt if dt.tzinfo else dt.replace(tzinfo=ET)


def _cancel_open_orders_for_symbol(trading_client: TradingClient, symbol: str) -> None:
    """Cancel every open order for *symbol* (best-effort; errors are logged, not raised)."""
    try:
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        for order in trading_client.get_orders(req):
            try:
                trading_client.cancel_order_by_id(str(order.id))
                print(f"    Cancelled order {order.id} for {symbol}")
            except Exception as exc:
                print(f"    Warn: cancel {order.id} failed: {exc}")
    except Exception as exc:
        print(f"    Warn: could not fetch open orders for {symbol}: {exc}")


def _poll_position_closed(trading_client: TradingClient, symbol: str) -> bool:
    """
    Poll Alpaca until the position for *symbol* is fully closed (qty == 0 or absent).

    Returns:
        True  – confirmed closed within _POLL_TIMEOUT_S seconds.
        False – timed out; position still appears open.
    """
    deadline = time.monotonic() + _POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            pos = trading_client.get_open_position(symbol)
            if float(pos.qty) == 0:
                return True
        except Exception:
            return True  # position not found → already closed
        time.sleep(_POLL_INTERVAL_S)
    return False


def _get_alpaca_positions(trading_client: TradingClient) -> dict[str, object]:
    """Return {symbol: Position} for every currently open Alpaca position."""
    return {p.symbol: p for p in trading_client.get_all_positions()}


def _order_exists_today(trading_client: TradingClient, client_order_id: str) -> bool:
    """
    Return True if an order with *client_order_id* was submitted today (ET).

    Checks ALL statuses (open, filled, cancelled) to catch idempotency violations
    regardless of how far the order progressed.
    """
    try:
        today_start = get_now_et().replace(hour=0, minute=0, second=0, microsecond=0)
        req = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            after=today_start,
            limit=500,
        )
        return any(o.client_order_id == client_order_id for o in trading_client.get_orders(req))
    except Exception:
        return False  # conservative default: let the caller try and handle any API-side rejection


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def reconcile_with_alpaca(trading_client: TradingClient, state: dict) -> None:
    """
    Synchronise local state with live Alpaca account state.

    * Alpaca position absent from local state → import as "imported_unknown_timing"
      with a best-effort exit time of entry_now + 7 days (next trading day at 15:30 ET).
    * Local position is open/pending_exit but Alpaca no longer holds it → mark closed.

    Saves state if any changes are made.
    """
    alpaca  = _get_alpaca_positions(trading_client)
    now_et  = get_now_et()
    changed = False

    # ── Import unknown Alpaca positions ───────────────────────────────────────
    for symbol, pos in alpaca.items():
        if symbol not in state["positions"]:
            try:
                exit_et = _compute_exit_time(now_et, trading_client)
            except Exception:
                # Calendar API failure: fall back to raw arithmetic
                exit_et = (now_et + timedelta(days=HOLD_DAYS)).replace(
                    hour=15, minute=30, second=0, microsecond=0
                )
            state["positions"][symbol] = {
                "symbol":                symbol,
                "entry_time_et":         now_et.isoformat(),
                "exit_time_et":          exit_et.isoformat(),
                "notional":              float(getattr(pos, "market_value", 0) or 0),
                "score":                 0.0,
                "entry_client_order_id": None,
                "entry_order_id":        None,
                "exit_client_order_id":  None,
                "exit_order_id":         None,
                "status":                "imported_unknown_timing",
            }
            print(
                f"  [reconcile] Imported unknown position: {symbol}"
                f"  exit_scheduled={exit_et.strftime('%Y-%m-%d %H:%M %Z')}"
            )
            changed = True

    # ── Mark closed any local positions Alpaca no longer holds ────────────────
    for symbol, rec in state["positions"].items():
        if rec["status"] in _ACTIVE_STATUSES and symbol not in alpaca:
            rec["status"] = "closed"
            print(f"  [reconcile] Marked closed (not in Alpaca): {symbol}")
            changed = True

    if changed:
        save_state(state)


# ---------------------------------------------------------------------------
# Sell logic
# ---------------------------------------------------------------------------

def _should_sell_now(rec: dict, now_et: datetime) -> bool:
    """
    Decide whether to attempt a sell for *rec* on this run.

    Priority order:
      1. status == "pending_exit"             → always retry (prior run failed/timed out).
      2. now_et > exit_time_et               → overdue; sell ASAP regardless of window.
      3. exit today AND in exit window        → on-schedule sell (15:20–15:55 ET).
    """
    if rec["status"] == "pending_exit":
        return True
    exit_et = _exit_time(rec)
    if now_et > exit_et:
        return True  # overdue — sell immediately when market is open
    if exit_et.date() == now_et.date() and is_in_exit_window(now_et):
        return True  # scheduled for today and we are in the exit window
    return False


def process_due_sells(
    trading_client: TradingClient,
    state: dict,
    now_et: datetime,
) -> tuple[int, int, int]:
    """
    Execute sells for all positions that are due, overdue, or pending retry.

    Sell sequence per symbol:
      1. Cancel any open orders for the symbol.
      2. Call close_position() to liquidate 100 % of the position.
      3. Poll until confirmed closed (or timeout).
      4. Update state immediately after each symbol; never batch writes.

    Args:
        trading_client: Authenticated TradingClient.
        state:          Loaded state dict (mutated in place).
        now_et:         Current ET time.

    Returns:
        (attempted, succeeded, failed)
    """
    attempted = succeeded = failed = 0
    alpaca = _get_alpaca_positions(trading_client)

    for symbol, rec in list(state["positions"].items()):
        if rec["status"] not in _ACTIVE_STATUSES:
            continue
        if not _should_sell_now(rec, now_et):
            continue
        if symbol not in alpaca:
            continue  # position already gone; reconcile() will mark it closed

        attempted += 1
        # Mark pending_exit BEFORE attempting so a crash mid-sell is recoverable
        rec["status"] = "pending_exit"
        save_state(state)

        print(f"  [sell] {symbol}  exit_due={_exit_time(rec).strftime('%Y-%m-%d %H:%M %Z')}")
        try:
            _cancel_open_orders_for_symbol(trading_client, symbol)

            try:
                trading_client.close_position(symbol)
            except Exception as exc:
                # close_position may error if the position was already liquidated on Alpaca's side;
                # _poll_position_closed will confirm the truth.
                print(f"    close_position raised: {exc} — verifying via poll ...")

            if _poll_position_closed(trading_client, symbol):
                rec["status"] = "closed"
                print(f"  [sell] ✓ {symbol} confirmed closed")
                succeeded += 1
            else:
                print(f"  [sell] ✗ {symbol} still open after {_POLL_TIMEOUT_S}s — will retry next run")
                failed += 1

        except Exception as exc:
            print(f"  [sell] ✗ {symbol} unexpected error: {exc} — will retry next run")
            failed += 1

        save_state(state)  # persist updated status after each symbol

    return attempted, succeeded, failed


# ---------------------------------------------------------------------------
# Buy logic
# ---------------------------------------------------------------------------

def _entry_client_order_id(symbol: str, now_et: datetime) -> str:
    return f"SBV3-ENTRY-{now_et.strftime('%Y%m%d')}-{symbol}"


def _exit_client_order_id(symbol: str, exit_et: datetime) -> str:
    return f"SBV3-EXIT-{exit_et.strftime('%Y%m%d')}-{symbol}"


def process_buys(
    trading_client: TradingClient,
    state: dict,
    candidates: list[dict],
    now_et: datetime,
) -> tuple[int, int, int]:
    """
    Place buy orders for eligible scan candidates.

    Guards (all must pass before any orders are placed):
      - now_et is within the entry window (15:25–15:40 ET).
      - Market is currently open.
      - Open position count < MAX_OPEN_POSITIONS.
      - Daily buy count < MAX_NEW_BUYS_PER_DAY.

    Candidate filtering:
      - score >= MIN_SCORE (120).
      - Symbol not already held (Alpaca positions OR local active state).
      - No order with today's client_order_id already submitted (idempotency).

    Candidates are sorted by score descending; top N are selected.

    Args:
        trading_client: Authenticated TradingClient.
        state:          Loaded state dict (mutated in place).
        candidates:     List of dicts: {symbol, score, target_notional_dollars}.
        now_et:         Current ET time.

    Returns:
        (attempted, succeeded, failed)
    """
    if not is_in_entry_window(now_et):
        return 0, 0, 0
    if not is_market_open(trading_client):
        print("  [buy] Market is closed — skipping buys")
        return 0, 0, 0

    attempted = succeeded = failed = 0

    alpaca       = _get_alpaca_positions(trading_client)
    local_active = {sym for sym, rec in state["positions"].items() if rec["status"] in _ACTIVE_STATUSES}
    held         = set(alpaca.keys()) | local_active

    available_slots = max(0, MAX_OPEN_POSITIONS - len(held))
    if available_slots == 0:
        print(f"  [buy] No slots available ({len(held)}/{MAX_OPEN_POSITIONS} open)")
        return 0, 0, 0

    today_str      = now_et.strftime("%Y-%m-%d")
    bought_today   = list(state["daily_buys"].get(today_str, []))
    remaining_daily = MAX_NEW_BUYS_PER_DAY - len(bought_today)
    if remaining_daily <= 0:
        print(f"  [buy] Daily buy limit reached ({MAX_NEW_BUYS_PER_DAY}/day)")
        return 0, 0, 0

    max_buys = min(available_slots, remaining_daily)

    eligible = [
        c for c in candidates
        if float(c.get("score", 0)) >= MIN_SCORE and c["symbol"] not in held
    ]
    eligible.sort(key=lambda c: float(c["score"]), reverse=True)
    to_buy = eligible[:max_buys]

    if not to_buy:
        print(
            f"  [buy] No eligible candidates "
            f"(need score>={MIN_SCORE}, not already held, {available_slots} slot(s) free)"
        )
        return 0, 0, 0

    for cand in to_buy:
        symbol   = cand["symbol"]
        notional = float(cand["target_notional_dollars"])
        score    = float(cand["score"])
        coid     = _entry_client_order_id(symbol, now_et)

        # Second idempotency check (symbol may have been added mid-loop by a parallel run)
        if symbol in held:
            print(f"  [buy] Skip {symbol} — already held")
            continue
        if _order_exists_today(trading_client, coid):
            print(f"  [buy] Skip {symbol} — order {coid} already submitted today")
            continue

        attempted += 1
        try:
            order = trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    notional=notional,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                    client_order_id=coid,
                )
            )

            entry_et = now_et.replace(second=0, microsecond=0)
            exit_et  = _compute_exit_time(entry_et, trading_client)

            state["positions"][symbol] = {
                "symbol":                symbol,
                "entry_time_et":         entry_et.isoformat(),
                "exit_time_et":          exit_et.isoformat(),
                "notional":              notional,
                "score":                 score,
                "entry_client_order_id": coid,
                "entry_order_id":        str(order.id),
                "exit_client_order_id":  _exit_client_order_id(symbol, exit_et),
                "exit_order_id":         None,
                "status":                "open",
            }
            bought_today.append(symbol)
            state["daily_buys"][today_str] = bought_today
            held.add(symbol)
            save_state(state)

            print(
                f"  [buy] ✓ {symbol}"
                f"  notional=${notional:.0f}  score={score:.0f}"
                f"  exit={exit_et.strftime('%Y-%m-%d %H:%M %Z')}"
            )
            succeeded += 1

        except Exception as exc:
            print(f"  [buy] ✗ {symbol}: {exc}")
            failed += 1

    return attempted, succeeded, failed


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_execution(candidates: list[dict], now: datetime | None = None) -> None:
    """
    Top-level execution function.  Call once per scheduled run.

    Execution order (immutable):
        1. Reconcile local state with live Alpaca positions.
        2. Process due/overdue sells (ALWAYS before buys).
        3. Process buys (only if within entry window and market is open).
        4. Print run summary.

    Args:
        candidates:
            Picks from the supabot_v3.py scan.  Each dict must contain::

                {
                    "symbol":                 str,
                    "score":                  float,
                    "target_notional_dollars": float,
                }

            The caller is responsible for mapping supabot_v3.py output into
            this format.  Pass an empty list to run reconcile + sells only.

        now:
            Override the current time (for unit tests).  Pass ``None`` (default)
            to use the real system clock.

    GitHub Actions scheduling note:
        This function is designed to be called on every workflow run.
        - A 14:00 ET run: reconciles state and processes any due/overdue sells;
          buys are skipped (outside entry window).
        - A 15:30 ET run: reconciles, sells (on-schedule exits), then places buys.
        Adding a dedicated 15:30 ET job in the workflow guarantees both sell
        and buy timing requirements are met.
    """
    client = _make_client()
    now_et = get_now_et(now)
    paper  = _is_paper()

    sep = "=" * 64
    print(f"\n{sep}")
    print(f"  alpaca_execution_v1  |  {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(
        f"  mode={'PAPER' if paper else 'LIVE '}  |  "
        f"max_positions={MAX_OPEN_POSITIONS}  "
        f"max_buys/day={MAX_NEW_BUYS_PER_DAY}  "
        f"min_score={MIN_SCORE}"
    )
    print(sep)

    state = load_state()

    # ── 1. Reconcile ─────────────────────────────────────────────────────────
    print("[1/4] Reconciling state with Alpaca ...")
    try:
        reconcile_with_alpaca(client, state)
    except Exception as exc:
        print(f"  [reconcile] Error (non-fatal, continuing): {exc}")

    # ── 2. Sells (always before buys) ────────────────────────────────────────
    print("[2/4] Processing due sells ...")
    if is_market_open(client):
        sell_att, sell_ok, sell_fail = process_due_sells(client, state, now_et)
    else:
        print("  Market is closed — sells deferred to next run when market opens")
        sell_att = sell_ok = sell_fail = 0

    # ── 3. Buys ──────────────────────────────────────────────────────────────
    print("[3/4] Processing buys ...")
    if is_in_entry_window(now_et):
        buy_att, buy_ok, buy_fail = process_buys(client, state, candidates, now_et)
    else:
        print(
            f"  Outside entry window "
            f"({_ENTRY_START[0]}:{_ENTRY_START[1]:02d}–"
            f"{_ENTRY_END[0]}:{_ENTRY_END[1]:02d} ET) — skipping buys"
        )
        buy_att = buy_ok = buy_fail = 0

    # ── 4. Summary ───────────────────────────────────────────────────────────
    open_count = sum(1 for rec in state["positions"].values() if rec["status"] in _ACTIVE_STATUSES)
    print("[4/4] Run summary:")
    print(f"  Sells : attempted={sell_att}  succeeded={sell_ok}  failed={sell_fail}")
    print(f"  Buys  : attempted={buy_att}  succeeded={buy_ok}  failed={buy_fail}")
    print(f"  Open positions after run: {open_count}/{MAX_OPEN_POSITIONS}")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run with no candidates: reconcile + sells only.  Useful for manual sell-only runs.
    print("Running alpaca_execution_v1 in CLI mode (reconcile + sells only, no buys).")
    run_execution(candidates=[])
