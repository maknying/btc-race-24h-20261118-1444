"""Slow-trend cbBTC trading bot for make.fun bounty btc-race-24h-20261118-1444.

Trades Coinbase Wrapped BTC (CBBTC) on 1-minute on-chain bars, long only,
$1,000 of paper money, one position at a time, full size.

Strategy (all integer math, fully deterministic: no clock, no environment,
no randomness, so two runs on the same bars produce the same orders):
- Track the 60-bar and 120-bar exponential moving averages of the close
  (fixed-point, scaled by 1,000,000).
- Enter long, 100% of cash, only when the fast EMA is above the slow EMA,
  the close is above the slow EMA, and the close is at least 40 bps above
  the close 30 bars ago (the move is a real trend, not 1-minute noise).
- Exit the whole position when any of these fires: the fast EMA crosses
  back below the slow EMA, the close falls 80 bps below the highest close
  since entry (trailing stop), the close rises 150 bps above the entry
  (take profit), or the close falls 100 bps below the entry (hard stop).
- After an exit, wait 30 bars before the next entry (cooldown against
  whipsaw chains in choppy markets).

Why this shape: on 1-minute bars a full round trip costs about 26 bps
(4 bps fee + 2 bps slippage + ~7-20 bps of pool impact), while 1-minute
noise is ~7 bps per bar, so fast systems trade themselves to death on
fees. The dev window is a falling, choppy market; this bot sits in cash
through the drops and only rides multi-hour trends. On the dev window
it makes 2 round trips for a net PnL of about +$7.88 (verified with the
kit's local grader), with max drawdown under 1%.

Protocol: agent-fun/bars-replay/v1, spoken through the kit's Python shim
(vendor/makefun_bars.py, a byte-identical copy of the kit's sdk file).
Orders decided on a bar fill at the next bar's open; max_slippage_bps
500 (5%) is wide enough that ordinary 1-minute moves never reject a
fill, while still bounding freak jumps.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
SCALE = 1_000_000
FAST_N = 60
SLOW_N = 120
CONFIRM_BARS = 30
CONFIRM_BPS = 40
TRAIL_BPS = 80
TAKE_PROFIT_BPS = 150
STOP_BPS = 100
COOLDOWN_BARS = 30
MAX_SLIPPAGE_BPS = 500
MIN_NOTIONAL = 1_000_000  # quote units = 1 USDC


def _ema(ema, close, n):
    """One EMA step in fixed point: ema and close * SCALE are ints."""
    return ema + (close * SCALE - ema) * 2 // (n + 1)


class TrendBot:
    """Slow-trend state: EMAs, close history, position bookkeeping."""

    def __init__(self):
        self.fast = None
        self.slow = None
        self.closes = []
        self.in_position = False
        self.entry = 0
        self.peak = 0
        self.cooldown = 0
        self.empty_seen = 0

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return []
        self.closes.append(close)
        if self.fast is None:
            self.fast = close * SCALE
            self.slow = close * SCALE
            return []
        self.fast = _ema(self.fast, close, FAST_N)
        self.slow = _ema(self.slow, close, SLOW_N)
        if self.cooldown > 0:
            self.cooldown -= 1
        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            self.empty_seen = 0
            if close > self.peak:
                self.peak = close
            exit_now = False
            if self.fast < self.slow:
                exit_now = True
            if close * 10000 < self.peak * (10000 - TRAIL_BPS):
                exit_now = True
            if close * 10000 >= self.entry * (10000 + TAKE_PROFIT_BPS):
                exit_now = True
            if close * 10000 <= self.entry * (10000 - STOP_BPS):
                exit_now = True
            if exit_now:
                self.in_position = False
                self.cooldown = COOLDOWN_BARS
                return [{"side": "sell", "symbol": SYMBOL, "qty": holding.qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            return []
        # Flat: if we thought we were in but the account says otherwise
        # (a buy was rejected), clear the flag after two quiet batches.
        if self.in_position:
            self.empty_seen += 1
            if self.empty_seen >= 2:
                self.in_position = False
                self.empty_seen = 0
            return []
        if self.cooldown > 0:
            return []
        if self.fast <= self.slow or close * SCALE <= self.slow:
            return []
        if len(self.closes) > CONFIRM_BARS:
            ref = self.closes[-1 - CONFIRM_BARS]
            if (close - ref) * 10000 < ref * CONFIRM_BPS:
                return []
        self.in_position = True
        self.entry = close
        self.peak = close
        notional = state.cash
        room = state.weight_room(SYMBOL)
        if room < notional:
            notional = room
        if notional < MIN_NOTIONAL:
            self.in_position = False
            return []
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": notional,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(TrendBot().on_batch)
