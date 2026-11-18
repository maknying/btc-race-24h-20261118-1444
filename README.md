# Slow-trend cbBTC bot — race a BTC trading bot live for 24 hours

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/maknying/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/maknying/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

Entry for make.fun bounty **btc-race-24h-20261118-1444** ("Race a BTC trading bot live for 24 hours").
Free entry, no entry fee. Entries close 2026-11-18 20:44 UTC; the 24-hour live race starts 15 minutes later.

## What it is

A slow trend-following bot that trades Coinbase Wrapped BTC (cbBTC) on
1-minute on-chain bars with $1,000 of paper money (nothing traded for
real), long only, one position at a time, full size.

- `main.py` — entrypoint (Python 3.13, standard library only). Speaks
  agent-fun/bars-replay/v1 through the kit's Python shim in `vendor/`.
- `vendor/makefun_bars.py` — byte-identical copy of the kit's
  `sdk/makefun_bars.py` (the bars-replay protocol shim).

## Strategy

- Enter long, 100% of cash, only when the 60-bar EMA is above the
  120-bar EMA, the close is above the slow EMA, and the close is at
  least 40 bps above the close 30 bars ago.
- Exit the whole position on: fast EMA crossing back below slow EMA,
  an 80 bps trailing stop from the highest close since entry, a 150 bps
  take profit, or a 100 bps hard stop.
- 30-bar cooldown after every exit, to avoid whipsaw chains in chop.
- All math is integer fixed-point; no clock, environment or randomness,
  so two runs on the same bars produce the same orders.

Why slow: a full round trip costs about 26 bps (4 bps fee + 2 bps
slippage + pool impact) while 1-minute noise is ~7 bps a bar, so fast
systems trade themselves to death on fees. On the published dev window
(BTC down 2.8% over 24h) this bot sits in cash through the drops and
rides the multi-hour recovery: 2 round trips, net PnL about +$7.88,
max drawdown under 1% (verified with the kit's local grader).

## Run it locally

```
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . --driver process
```
