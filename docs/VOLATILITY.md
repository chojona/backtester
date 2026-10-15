# Realized-volatility measurements

This layer measures ex post variation; it does not forecast, trade, fit parameters,
or establish predictive power. Synthetic verification is not market validation.

`raw Bar -> causal log returns -> realized measurements -> VolatilityRecord`

`backtester/volatility.py` contains standalone estimators and `RealizedVolatility`.
It reuses `Bar`, `SessionCalendar` (including dated subclasses), and raw constituent
prices from the existing roll selector. Execution and existing ATR are untouched.
The feature-record schema is versioned as `realized-volatility-1` in CLI reports.

## Definitions and interpretation

Prices must be positive and finite. Scalar return functions take an explicitly
ordered, equal-frequency, gap-free sequence. They reject NaN/Inf; callers must split
at unavailable observations, never fill missing returns with zero. Empty samples
return `None`; BPV/TBPV also require at least two observations. No annualization,
demeaning, drift adjustment, or percentage scaling is applied.

For n log returns r_i over a unit-normalized measurement window:

| Field / function | Exact definition | Interpretation |
|---|---|---|
| `log_return(p,q)` | log(q/p) | Dimensionless return; log1p near equality, difference of logs for extreme ratios |
| `rv_1m` / `realized_variance` | sum r_i² | Total quadratic-variation proxy, continuous plus jumps |
| `rv_5m`, `rv_15m` | sum (sum of the k constituent minute returns)², k=5,15 | Coarser nonoverlapping RV; not a sum of minute RVs |
| `bpv` / `bipower_variation` | (pi/2) sum from i=2 to n of abs(r_i r_(i-1)) | Continuous-variation proxy under diffusion plus finite-activity jumps |
| `jump` / `jump_variation` | max(RV-BPV,0) | Nonnegative jump proxy; no test statistic or proof of a jump |
| `rs_positive`, `rs_negative` / `semivariances` | sum r_i² 1[r_i>0], sum r_i² 1[r_i<0] | Signed contributions to variation; zeros contribute to neither |
| `quarticity` / `realized_quarticity` | (n/3) sum r_i⁴ | Fourth-power variation proxy; informs measurement uncertainty under continuous assumptions |
| `realized_range` | sum log(H_i/L_i)² / (4 log 2) | Sum of minute Parkinson range variances using continuous-path normalization |
| `rv_rth`, `rv_overnight`, `rv_post_rth` | sum r_i² for destination bars in the named calendar segment | Segment-specific total variation |
| `rv_intraday_to_now` | sum r_i² for completed bars through record timestamp | Cumulative causal RV, with the same coverage rule as rv_1m |

The BPV definition is the uncorrected adjacent version, without n/(n-1)
finite-sample adjustment or staggering. Pairs never cross a gap, halt, session,
contract, or calendar segment. Consequently a full-session BPV sums segment BPVs.
This convention is estimator `bpv-segment-v1.0.0`: returns are log(close/reference),
with the first observed bar using its open and later bars using the preceding close
only when adjacent on the same contract and trading date. A boundary bar's return
belongs to its destination segment. BPV uses `(pi/2) * sum(abs(r[i-1] * r[i]))`
for adjacent one-minute returns in the same Overnight, RTH, or Post-RTH segment;
there is no `n/(n-1)` correction. A gap, unknown bar, contract change, or calendar
segment boundary removes that pair. Fewer than one eligible pair yields null.
The retained `results/databento-nq-full-history/volatility-by-session.csv` uses
legacy `bpv-all-adjacent-v0.0.0`, which includes the two segment-boundary pairs.
`scripts/version_nq_bpv.py` writes a separately versioned derived table and
manifest from the unchanged consolidated history.
See [Barndorff-Nielsen and Shephard (2004)](https://shephard.scholars.harvard.edu/publications/power-and-bipower-variation-stochastic-volatility-and-jumps).
Its asymptotic robustness is conditional on model assumptions, not assured at 1m.
RV = RS+ + RS- up to rounding; BPV may exceed RV in finite samples.

TBPV implements normalized TMPV[1,1] from Definition 2.2, equation (2.10), of
[Corsi, Pirino and Renò](https://openaccess.city.ac.uk/4435/1/CorsiPirinoReno_TBV_sub2010.pdf):

`(pi/2) sum abs(r_i r_(i-1)) 1[r_i²<=theta_i] 1[r_(i-1)²<=theta_(i-1)]`.

This is basic TBPV, not corrected C-TBPV or their jump test. The standalone
function accepts positive finite squared thresholds per observation. The stream
accepts one fixed ex ante squared-return threshold for the run and records it;
without a configured threshold, TBPV is null. No threshold is fitted. A single
finite-frequency cutoff does not itself establish asymptotic consistency. For
an asymptotic threshold family, the paper requires Theta(delta)->0 and
`delta*log(1/delta)/Theta(delta)->0`, with a bounded positive local multiplier.
Adaptive local scale estimation and bias correction are deferred; a scalar caller
must establish the point-in-time provenance of any supplied threshold sequence.

RQ uses the *observed window* as a unit interval. For physical sampling interval
Delta, integrated physical-time quarticity instead scales as `sum r_i⁴/(3 Delta)`.
Do not compare a 5-minute prefix's RQ directly with a full day's RQ without its
window metadata. `2*RQ/n` is an asymptotic RV error-variance approximation only in
a continuous, noiseless model. Jumps and noise invalidate that interpretation;
this layer supplies no confidence intervals. See
[Barndorff-Nielsen and Shephard, Estimating quadratic variation using realized variance](https://shephard.scholars.harvard.edu/sites/g/files/omnuum7741/files/jae02.pdf).

Semivariances describe directional variation, not signed expected returns or pure
jump variation; see [Measuring downside risk: realised semivariance](https://shephard.scholars.harvard.edu/publications/measuring-downside-risk-realised-semivariance).
The range sum assumes effectively continuous intrabar extrema, negligible drift
and noise. Tick-sampled OHLC does not satisfy that idealization exactly. We do not
claim the discretely corrected Christensen–Podolskij estimator: its normalization
needs intrabar sampling information absent from these candles. See
[Christensen and Podolskij (2007)](https://pure.au.dk/portal/da/publications/realized-range-based-estimation-of-integrated-variance/).
High/low variation misses jumps between bars; range and close-return RV measure
different aspects of the observed path. Neither has guaranteed dominance here.

## Time, sampling, coverage and contract rules

Call `update(raw_bar, as_of=aware_time)` once per completed minute in chronological
order. The record timestamp is `bar.end`, never the bar-open timestamp.
Future/incomplete bars, duplicates, overlaps, off-minute timestamps, unsupported
durations, invalid prices and bars outside the supplied calendar are rejected.
The API takes a `Bar`; `SelectedBar` must be unpacked explicitly via `.raw`.
It cannot detect adjusted prices disguised as raw bars. Configuration (calendar
and threshold) must be fixed during the run; `as_of` must represent the caller's
actual information cutoff. Historical vendor corrections and publication latency
are not modeled by a nominal bar-end availability convention.

Within a session/contract, consecutive traded-grid bars use previous close to
current close, including an RTH boundary's return in its destination segment.
The very first observed bar uses its own open to close. After a missing bar,
UNKNOWN bar, scheduled halt, session change or contract change, restart at the
current observed open; do not bridge the discontinuity. A scheduled closure's
price change is excluded from intraday variation. No close from yesterday enters
today's opening minute. An exchange opening gap would require a separate
same-contract gap feature; it is intentionally outside this intraday measure.

The calendar defines the expected minute grid from ETH open to the current bar.
`prefix_complete` requires every expected bar, with no UNKNOWN coverage.
`missing_bars_to_now` counts absent scheduled bars, including missing beginning
coverage; `unknown_bars` counts supplied bars with UNKNOWN coverage. Missing future
bars are never counted before they are due. Nonempty incomplete prefixes have
null canonical full-session RV/BPV/TBPV/RS/RQ/range and coarse RV. `observed_rv`
retains the sum of available within-run returns, explicitly a diagnostic, not an
estimate of an unobserved complete window. A gap cannot be repaired by future bars.

Segment measurements have independent prefix coverage, so RTH can be valid even
when overnight input is absent. Unobserved segments are null. Already completed
segments remain frozen. `OVERNIGHT` means pre-RTH only; `POST_RTH` is separate.
`session_complete` additionally requires reaching the calendar's ETH close.
A valid morning prefix is not a complete daily training target.

Only explicit provider-evidenced `NO_TRADE` bars may represent flat no-trade
minutes; they are counted separately. `UNVERIFIED` source bars are accepted but
retain their input provenance in ingestion reports: grid coverage does not certify
vendor truth, trade-level completeness, or a historical calendar.

5/15-minute sampling uses nonoverlapping blocks anchored to `segment_open` from
`SessionInfo`, not UTC midnight. Gold's 08:20 segment therefore anchors a 15m block
at 08:20. A block needs all k consecutive minute returns; it cannot cross a segment,
halt, gap, session or roll. The block return telescopes between the first return's
reference price and the final close. Incomplete final tails are omitted, with
`samples_*` and `covered_minutes_*` making the smaller measurement support explicit.
Comparisons between frequencies must use matched support. These fields are not
annualized extrapolations of the unobserved remainder.

Contract changes reset measurement state even within the same trading date. A
mid-session new-contract prefix is incomplete, with observed diagnostics retained;
old and new contracts are never merged into one daily target. The CLI reports
separate last records per (trading date, contract), using the existing causal roll
selector and its expiration/paired-open requirements. Do not feed retrospective
back-adjusted or forward-additive research prices into log-return measurement.
Constant additive adjustments change percentage returns even without a roll jump.

## Causal intraday normalization

For each scheduled minute slot j, the profile variance share is

`sum_prior_complete_sessions r_(d,j)² / sum_prior_complete_sessions RV_d`.

This equals the historical mean slot variance divided by historical mean daily RV.
`profile_volatility_share` is its square root (root relative variance, not shares
that sum to one). Variance shares sum to one over the matching calendar grid.
The current session is never in its own reference set. Only previously completed,
fully covered, single-contract sessions from this instrument and with identical
relative-time/segment grids qualify. Clean previous contracts may contribute.
Early closes and different DST-length grids are not silently pooled. The record
contains reference count and latest reference availability time. No history or a
zero historical denominator gives null. This is a transparent descriptive profile,
not a fitted forecasting model. Historical profile storage currently grows with the
run; session calculations retain minute returns and recompute prefix sums. Larger
research runs should add bounded reference windows and incremental storage under
separate tests before tick-scale use.

## Why retain multiple measurements?

Minute, 5m and 15m RV let future studies examine sensitivity to sampling noise and
path cancellation. BPV/TBPV and jump proxies can separate candidate continuous and
discontinuous behavior under explicit assumptions. RS-/RS+ characterize asymmetry.
Quarticity can inform HARQ-style measurement-error weighting under appropriate
assumptions. Range uses extrema absent from close returns. Session decomposition
and lagged profiles describe time-of-day variation.

Future HAR, MS-HAR, Realized-GARCH or ML consumers should use complete daily targets,
lagged feature availability timestamps, coverage fields and matched supports.
Regime and cross-market studies also need synchronized availability. These are
possible inputs, not claims of predictive benefit. No model, optimization,
profitability study, ATR research feature, or significance test is implemented.

Minute OHLCV loses trade ordering, bid/ask bounce information, quotes, depth,
intrabar sampling counts and publication history. Realized kernels can be built
from suitable high-frequency price samples, but coarse candles cannot reconstruct
the noise autocovariances or justify bandwidth selection. True microstructure/LOB
estimators need trades/quotes/depth and synchronization; they are deferred.

## Deterministic local report

```sh
.venv/bin/python -m backtester volatility --data data/synthetic_NQ_1m.csv --symbol NQ
.venv/bin/python -m backtester volatility --data data/synthetic_NQ_1m.csv --symbol NQ \
  --as-of 2026-01-04T23:05:00Z
```

These commands print JSON to standard output; redirect it to a local file under
`results/` to retain a report. The CLI accepts NQ, ES and GC with one-minute input.
The second command reports only five completed fixture minutes. `--config` reuses
the existing raw-input/calendar/roll configuration; `--tbpv-squared-threshold`
optionally freezes a research cutoff. Output includes source hash, calendar source,
ingestion integrity and last records per session/contract. Full-file ingestion
validation may reject malformed future input, but feature values consume only the
cutoff prefix. The report does not submit orders or generate research labels.
See `docs/volatility-example.json` for the full two-session fixture report, including
a prior-session-normalized profile reference on the second session.

## Existing infrastructure limitations and real-data acceptance

`SessionCalendar` is a configurable weekday template, not a certified calendar.
Its default equity pause is obsolete for current NQ. The bounded dated adapter
currently only supports NQ; ES and GC need separately reviewed dated schedules
before real-market acceptance. Gold RTH is an explicit research convention.
Contract syntax validation is not a listing/expiry database. Fixed rolls can defer
to the first observed session bar; liquidity rolls need complete prior matched
coverage and raw paired opens. Bar positivity is stricter here than in execution,
which permits negative futures prices. Back-adjusted-input provenance and revised
historical bars cannot be inferred from price values alone.

The retained September 14–25, 2026 NQ acquisition passed independent raw-data,
calendar-boundary, roll, arithmetic and causal-prefix checks. The
[dated acceptance report](acceptance/databento-2026-10-07.md) records ten complete
active sessions, 13,800 traded minutes and one roll. Early closes, DST transitions,
TBPV and other instruments were not accepted by that trial. Provider-level and
unscheduled-halt limitations remain explicit.

Follow [DATABENTO.md](DATABENTO.md) for new acquisition and audit steps, or
[HISTORY.md](HISTORY.md) for full-history preparation. For a reviewed local dataset,
replace `ID` with its acquisition identifier and run:

```sh
.venv/bin/python -m backtester volatility \
  --data data/normalized/databento/NQ/ID/bars.csv --symbol NQ \
  --config data/normalized/databento/NQ/ID/research-config.json
```

Before accepting results, independently calculate log returns, squared returns,
segment totals and 5m/15m endpoint returns for retained raw sample minutes, an RTH
boundary, an early close, and both sides of a roll. Check RV=RS++RS-, clipped jump
identity, missing/no-trade/UNKNOWN counts, and measured support. Compare prefix
reports at fixed cutoffs with truncated and future-perturbed copies; their records
must agree. Retain raw/normalized/report/config/calendar hashes and manual review
notes. Investigate frequency sensitivity and source corrections without tuning
parameters for attractive results. Repeat with licensed ES and GC data after dated
calendar support is extended. The existing bounded acceptance must not be
extended to new periods or instruments without their own evidence.


## Visual inspection

`python -m backtester volatility-charts` provides an optional Matplotlib report;
install `.[charts]` first. The command accepts the same data/config, raw-contract,
cutoff and TBPV-threshold conventions as `volatility`, plus a required new `--output`
directory. It writes separate comparison PNG/SVG plots, per-session OHLC/volume PNG/SVG
exports, an offline HTML chart viewer, and measurement JSON with input hash and
calendar source. The viewer provides raw 1/5/15-minute OHLC bars, synchronized
volume, zoom, pan, hover values, and separate intraday measurement charts.
The offline viewer bundles TradingView Lightweight Charts 5.1.0 with its Apache
license, NOTICE, source metadata, and visible attribution. Price and volume share
a resizable pane boundary. Every chart has independent time ranges and crosshairs, explicit zoom buttons,
and Reset view to fit all points and restore vertical autoscaling. Timeframe controls replace OHLC
and volume data only; research indicators retain their defined sampling frequency.
Complete 1,380-minute sessions contain 1,380/276/92 price and volume bars at
1m/5m/15m respectively. Aggregation preserves total volume and excludes incomplete
blocks and unknown bars. No new market data is fetched when switching intervals.

The default All sessions view joins selected active-contract sessions into one
timeline at every timeframe, with contract rolls marked and raw prices unchanged.
Intraday research lines stay separate at session boundaries; cumulative variance
restarts for each session. Individual sessions remain available in the selector.

When an individual session is selected, the 1H, 4H and 1D views use all complete downloaded sessions for the selected
raw contract. Hourly and four-hour bars start at the futures session open; the
scheduled closing tail is included. Daily bars cover one futures session, not
a midnight-to-midnight day. No bar combines contracts or incomplete sessions.

No chart code executes network requests, trading, or model fitting.

Only complete sessions enter the comparison figure. Details retain missing-return
breaks and show observed RV separately when canonical RV is unavailable. Contract
series are never visually joined. The profile panel uses the measurement layer's
lagged reference set; the first session has no profile. RTH shading follows observed
calendar-classified bars. The scalar measurements remain in log-return units in
JSON; displays use bp² (`RV * 1e8`) and volatility percent (`sqrt(RV) * 100`). The
report's coverage counts expose coarse sampling's omitted tails. Local data and
chart reports remain ignored by Git.
