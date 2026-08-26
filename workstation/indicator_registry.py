from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import sqrt
from typing import Any, Callable, Iterable, Mapping

import numpy as np
import pandas as pd


SeriesMap = dict[str, pd.Series]
IndicatorCalculator = Callable[[pd.DataFrame, Mapping[str, Any]], SeriesMap]


@dataclass(frozen=True)
class IndicatorPlugin:
    """Versioned, deterministic indicator contract.

    Plugins receive a normalized, completed-bar OHLCV frame and explicit
    parameters.  They cannot fetch data or place orders.  Every result remains
    aligned to the input index so callers can build an auditable feature store.
    """

    name: str
    version: str
    parameters: Mapping[str, Any]
    input_requirements: tuple[str, ...]
    output_series: tuple[str, ...]
    warmup: int
    normalization: str
    timeframe_compatibility: tuple[str, ...]
    visualization: Mapping[str, Any]
    calculator: IndicatorCalculator = field(repr=False, compare=False)

    def metadata(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("calculator", None)
        return value


class IndicatorRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, IndicatorPlugin] = {}

    @staticmethod
    def _key(name: str) -> str:
        return "_".join(str(name or "").strip().lower().replace("/", " ").split())

    def register(self, plugin: IndicatorPlugin, *, replace: bool = False) -> None:
        key = self._key(plugin.name)
        if not key:
            raise ValueError("Indicator name is required")
        if key in self._plugins and not replace:
            raise ValueError(f"Indicator already registered: {plugin.name}")
        if not plugin.version or not plugin.output_series or plugin.warmup < 0:
            raise ValueError(f"Invalid indicator contract: {plugin.name}")
        self._plugins[key] = plugin

    def get(self, name: str) -> IndicatorPlugin:
        key = self._key(name)
        if key not in self._plugins:
            raise KeyError(f"Unknown indicator: {name}")
        return self._plugins[key]

    def catalog(self) -> list[dict[str, Any]]:
        return [self._plugins[key].metadata() for key in sorted(self._plugins)]

    def calculate(
        self,
        name: str,
        candles: Iterable[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        plugin = self.get(name)
        frame = normalize_ohlcv(candles)
        missing = [item for item in plugin.input_requirements if item not in frame]
        if missing:
            return _failure(plugin, f"Missing inputs: {', '.join(missing)}", len(frame))
        merged = {**dict(plugin.parameters), **dict(parameters or {})}
        if len(frame) < max(plugin.warmup, 1):
            return _failure(
                plugin,
                f"At least {plugin.warmup} completed bars are required.",
                len(frame),
            )
        try:
            calculated = plugin.calculator(frame.copy(), merged)
        except Exception as exc:
            return _failure(plugin, f"{type(exc).__name__}: {exc}"[:300], len(frame))
        series: dict[str, list[float | None]] = {}
        latest: dict[str, float | None] = {}
        for output in plugin.output_series:
            raw = calculated.get(output)
            values = _aligned(raw, frame.index)
            series[output] = [_number_or_none(item) for item in values.tolist()]
            valid = values.dropna()
            latest[output] = _number_or_none(valid.iloc[-1]) if not valid.empty else None
        return {
            "success": True,
            "indicator": plugin.metadata(),
            "parameters": merged,
            "bars": len(frame),
            "series": series,
            "latest": latest,
            "paper_only": True,
            "live_execution": False,
        }

    def calculate_many(
        self,
        requests: Iterable[str | tuple[str, Mapping[str, Any]]],
        candles: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        rows = list(candles)
        results: dict[str, Any] = {}
        for request in requests:
            if isinstance(request, tuple):
                name, parameters = request
            else:
                name, parameters = request, None
            results[self._key(name)] = self.calculate(name, rows, parameters=parameters)
        return {
            "success": all(row.get("success") for row in results.values()),
            "results": results,
            "paper_only": True,
            "live_execution": False,
        }


def normalize_ohlcv(candles: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for position, candle in enumerate(candles):
        lower = {str(key).lower(): value for key, value in dict(candle).items()}
        try:
            row = {
                "time": lower.get("time", lower.get("timestamp", position)),
                "open": float(lower["open"]),
                "high": float(lower["high"]),
                "low": float(lower["low"]),
                "close": float(lower["close"]),
                "volume": float(lower.get("volume") or 0.0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if not all(np.isfinite(row[key]) for key in ("open", "high", "low", "close", "volume")):
            continue
        if row["high"] < row["low"] or not row["low"] <= row["open"] <= row["high"] or not row["low"] <= row["close"] <= row["high"]:
            continue
        rows.append(row)
    return pd.DataFrame(rows, columns=("time", "open", "high", "low", "close", "volume"))


def _failure(plugin: IndicatorPlugin, message: str, bars: int) -> dict[str, Any]:
    return {
        "success": False,
        "indicator": plugin.metadata(),
        "bars": bars,
        "series": {},
        "latest": {},
        "message": message,
        "paper_only": True,
        "live_execution": False,
    }


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _aligned(value: Any, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.reindex(index)
    if np.isscalar(value):
        return pd.Series([value] * len(index), index=index, dtype="float64")
    values = list(value or [])
    if len(values) < len(index):
        values = [np.nan] * (len(index) - len(values)) + values
    return pd.Series(values[-len(index) :], index=index, dtype="float64")


def _sma(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    return {"sma": frame.close.rolling(period).mean()}


def _ema(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    return {"ema": frame.close.ewm(span=period, adjust=False, min_periods=period).mean()}


def _wma_series(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(period).apply(lambda values: float(np.dot(values, weights) / weights.sum()), raw=True)


def _wma(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    return {"wma": _wma_series(frame.close, int(p.get("period", 20)))}


def _hma(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = max(2, int(p.get("period", 20)))
    half = _wma_series(frame.close, max(1, period // 2))
    full = _wma_series(frame.close, period)
    raw = 2.0 * half - full
    return {"hma": _wma_series(raw, max(1, int(sqrt(period))))}


def _vwap(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    typical = (frame.high + frame.low + frame.close) / 3.0
    denominator = frame.volume.rolling(period).sum().replace(0, np.nan)
    return {"vwap": (typical * frame.volume).rolling(period).sum() / denominator}


def _anchored_vwap(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    anchor = max(0, min(int(p.get("anchor_index", 0)), len(frame) - 1))
    typical = (frame.high + frame.low + frame.close) / 3.0
    volume = frame.volume.copy()
    numerator = (typical.iloc[anchor:] * volume.iloc[anchor:]).cumsum()
    denominator = volume.iloc[anchor:].cumsum().replace(0, np.nan)
    avwap = pd.Series(np.nan, index=frame.index, dtype=float)
    avwap.iloc[anchor:] = (numerator / denominator).values
    deviation = (typical.iloc[anchor:] - avwap.iloc[anchor:]).expanding().std(ddof=0)
    upper = avwap.copy()
    lower = avwap.copy()
    bands = float(p.get("bands", 1.0))
    upper.iloc[anchor:] = avwap.iloc[anchor:] + bands * deviation.values
    lower.iloc[anchor:] = avwap.iloc[anchor:] - bands * deviation.values
    return {"anchored_vwap": avwap, "upper_band": upper, "lower_band": lower}


def _rsi_values(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    result = 100 - 100 / (1 + rs)
    return result.where(loss.ne(0), 100.0)


def _rsi(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    return {"rsi": _rsi_values(frame.close, int(p.get("period", 14)))}


def _stoch_rsi(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 14))
    smooth = int(p.get("smooth", 3))
    rsi = _rsi_values(frame.close, period)
    low = rsi.rolling(period).min()
    high = rsi.rolling(period).max()
    raw = 100 * (rsi - low) / (high - low).replace(0, np.nan)
    return {"stoch_rsi": raw, "signal": raw.rolling(smooth).mean()}


def _macd(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    fast, slow, signal = int(p.get("fast", 12)), int(p.get("slow", 26)), int(p.get("signal", 9))
    fast_line = frame.close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_line = frame.close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd = fast_line - slow_line
    signal_line = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return {"macd": macd, "signal": signal_line, "histogram": macd - signal_line}


def _true_range(frame: pd.DataFrame) -> pd.Series:
    previous = frame.close.shift(1)
    return pd.concat((frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()), axis=1).max(axis=1)


def _atr_values(frame: pd.DataFrame, period: int) -> pd.Series:
    return _true_range(frame).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _atr(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    return {"atr": _atr_values(frame, int(p.get("period", 14)))}


def _adx(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 14))
    up = frame.high.diff()
    down = -frame.low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index)
    atr = _atr_values(frame, period).replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}


def _bollinger(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period, deviations = int(p.get("period", 20)), float(p.get("deviations", 2.0))
    middle = frame.close.rolling(period).mean()
    std = frame.close.rolling(period).std(ddof=0)
    return {"middle": middle, "upper": middle + deviations * std, "lower": middle - deviations * std}


def _keltner(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period, multiplier = int(p.get("period", 20)), float(p.get("multiplier", 2.0))
    middle = frame.close.ewm(span=period, adjust=False, min_periods=period).mean()
    atr = _atr_values(frame, period)
    return {"middle": middle, "upper": middle + multiplier * atr, "lower": middle - multiplier * atr}


def _supertrend(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period, multiplier = int(p.get("period", 10)), float(p.get("multiplier", 3.0))
    atr = _atr_values(frame, period)
    midpoint = (frame.high + frame.low) / 2
    upper, lower = midpoint + multiplier * atr, midpoint - multiplier * atr
    line = pd.Series(np.nan, index=frame.index, dtype=float)
    direction = pd.Series(np.nan, index=frame.index, dtype=float)
    bullish = True
    for i in range(1, len(frame)):
        if pd.isna(atr.iloc[i]):
            continue
        if frame.close.iloc[i] > upper.iloc[i - 1]:
            bullish = True
        elif frame.close.iloc[i] < lower.iloc[i - 1]:
            bullish = False
        direction.iloc[i] = 1.0 if bullish else -1.0
        line.iloc[i] = lower.iloc[i] if bullish else upper.iloc[i]
    return {"supertrend": line, "direction": direction}


def _donchian(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    upper, lower = frame.high.rolling(period).max(), frame.low.rolling(period).min()
    return {"upper": upper, "middle": (upper + lower) / 2, "lower": lower}


def _ichimoku(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    conversion, base, span_b = int(p.get("conversion", 9)), int(p.get("base", 26)), int(p.get("span_b", 52))
    midpoint = lambda period: (frame.high.rolling(period).max() + frame.low.rolling(period).min()) / 2
    conversion_line, base_line = midpoint(conversion), midpoint(base)
    return {
        "conversion": conversion_line,
        "base": base_line,
        "span_a": ((conversion_line + base_line) / 2).shift(base),
        "span_b": midpoint(span_b).shift(base),
    }


def _cci(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    typical = (frame.high + frame.low + frame.close) / 3
    mean = typical.rolling(period).mean()
    deviation = typical.rolling(period).apply(lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True)
    return {"cci": (typical - mean) / (0.015 * deviation.replace(0, np.nan))}


def _mfi(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 14))
    typical = (frame.high + frame.low + frame.close) / 3
    flow = typical * frame.volume
    positive = flow.where(typical.diff() > 0, 0.0).rolling(period).sum()
    negative = flow.where(typical.diff() < 0, 0.0).rolling(period).sum().abs()
    ratio = positive / negative.replace(0, np.nan)
    return {"mfi": (100 - 100 / (1 + ratio)).where(negative.ne(0), 100.0)}


def _roc(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 12))
    return {"roc": frame.close.pct_change(period) * 100}


def _obv(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    direction = np.sign(frame.close.diff()).fillna(0)
    return {"obv": (direction * frame.volume).cumsum()}


def _cmf(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    spread = (frame.high - frame.low).replace(0, np.nan)
    multiplier = ((frame.close - frame.low) - (frame.high - frame.close)) / spread
    return {"cmf": (multiplier * frame.volume).rolling(period).sum() / frame.volume.rolling(period).sum().replace(0, np.nan)}


def _relative_volume(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    baseline = frame.volume.shift(1).rolling(period).mean().replace(0, np.nan)
    return {"relative_volume": frame.volume / baseline}


def _volume_profile(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    bins = max(3, int(p.get("bins", 20)))
    typical = (frame.high + frame.low + frame.close) / 3
    valid = frame.volume > 0
    if not valid.any() or typical.max() <= typical.min():
        poc = pd.Series(np.nan, index=frame.index)
    else:
        edges = np.linspace(float(typical.min()), float(typical.max()), bins + 1)
        groups = np.clip(np.digitize(typical, edges) - 1, 0, bins - 1)
        volumes = np.bincount(groups, weights=frame.volume, minlength=bins)
        index = int(np.argmax(volumes))
        value = float((edges[index] + edges[index + 1]) / 2)
        poc = pd.Series(value, index=frame.index)
    return {"point_of_control": poc}


def _zscore(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    mean, std = frame.close.rolling(period).mean(), frame.close.rolling(period).std(ddof=0)
    return {"zscore": (frame.close - mean) / std.replace(0, np.nan)}


def _realized_volatility(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period, annualization = int(p.get("period", 20)), float(p.get("annualization", 252.0))
    returns = np.log(frame.close / frame.close.shift(1))
    return {"realized_volatility": returns.rolling(period).std(ddof=0) * sqrt(annualization) * 100}


def _parkinson(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period, annualization = int(p.get("period", 20)), float(p.get("annualization", 252.0))
    squared = np.log(frame.high / frame.low.replace(0, np.nan)) ** 2
    variance = squared.rolling(period).mean() / (4 * np.log(2))
    return {"parkinson_volatility": np.sqrt(variance * annualization) * 100}


def _regression_slope(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 20))
    x = np.arange(period, dtype=float)
    slope = frame.close.rolling(period).apply(lambda values: float(np.polyfit(x, values, 1)[0]), raw=True)
    return {"regression_slope": slope}


def _correlation_beta(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    period = int(p.get("period", 30))
    benchmark = p.get("benchmark_close")
    if benchmark is None:
        raise ValueError("benchmark_close is required")
    benchmark_series = _aligned(benchmark, frame.index)
    asset_returns, benchmark_returns = frame.close.pct_change(), benchmark_series.pct_change()
    correlation = asset_returns.rolling(period).corr(benchmark_returns)
    covariance = asset_returns.rolling(period).cov(benchmark_returns)
    variance = benchmark_returns.rolling(period).var().replace(0, np.nan)
    return {"correlation": correlation, "beta": covariance / variance}


def _breadth(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    advances, declines = p.get("advances"), p.get("declines")
    if advances is None or declines is None:
        raise ValueError("advances and declines are required")
    advance_series, decline_series = _aligned(advances, frame.index), _aligned(declines, frame.index)
    total = (advance_series + decline_series).replace(0, np.nan)
    return {"advance_decline": advance_series - decline_series, "breadth_percent": 100 * advance_series / total}


def _options_oi(frame: pd.DataFrame, p: Mapping[str, Any]) -> SeriesMap:
    call_oi, put_oi = p.get("call_oi"), p.get("put_oi")
    if call_oi is None or put_oi is None:
        raise ValueError("call_oi and put_oi are required")
    calls, puts = _aligned(call_oi, frame.index), _aligned(put_oi, frame.index)
    return {
        "put_call_ratio": puts / calls.replace(0, np.nan),
        "call_oi_change": calls.diff(),
        "put_oi_change": puts.diff(),
    }


def _plugin(
    name: str,
    outputs: tuple[str, ...],
    warmup: int,
    calculator: IndicatorCalculator,
    parameters: Mapping[str, Any],
    *,
    inputs: tuple[str, ...] = ("close",),
    pane: str = "overlay",
    normalization: str = "raw",
) -> IndicatorPlugin:
    return IndicatorPlugin(
        name=name,
        version="1.0.0",
        parameters=dict(parameters),
        input_requirements=inputs,
        output_series=outputs,
        warmup=warmup,
        normalization=normalization,
        timeframe_compatibility=("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"),
        visualization={"pane": pane},
        calculator=calculator,
    )


def build_default_indicator_registry() -> IndicatorRegistry:
    registry = IndicatorRegistry()
    plugins = (
        _plugin("SMA", ("sma",), 20, _sma, {"period": 20}),
        _plugin("EMA", ("ema",), 20, _ema, {"period": 20}),
        _plugin("WMA", ("wma",), 20, _wma, {"period": 20}),
        _plugin("HMA", ("hma",), 24, _hma, {"period": 20}),
        _plugin("VWAP", ("vwap",), 20, _vwap, {"period": 20}, inputs=("high", "low", "close", "volume")),
        _plugin("Anchored VWAP", ("anchored_vwap", "upper_band", "lower_band"), 2, _anchored_vwap, {"anchor_index": 0, "bands": 1.0}, inputs=("high", "low", "close", "volume")),
        _plugin("RSI", ("rsi",), 15, _rsi, {"period": 14}, pane="oscillator", normalization="0_100"),
        _plugin("Stochastic RSI", ("stoch_rsi", "signal"), 31, _stoch_rsi, {"period": 14, "smooth": 3}, pane="oscillator", normalization="0_100"),
        _plugin("MACD", ("macd", "signal", "histogram"), 35, _macd, {"fast": 12, "slow": 26, "signal": 9}, pane="oscillator"),
        _plugin("ADX DMI", ("adx", "plus_di", "minus_di"), 28, _adx, {"period": 14}, inputs=("high", "low", "close"), pane="oscillator", normalization="0_100"),
        _plugin("ATR", ("atr",), 15, _atr, {"period": 14}, inputs=("high", "low", "close"), pane="oscillator"),
        _plugin("Bollinger Bands", ("middle", "upper", "lower"), 20, _bollinger, {"period": 20, "deviations": 2.0}),
        _plugin("Keltner", ("middle", "upper", "lower"), 20, _keltner, {"period": 20, "multiplier": 2.0}, inputs=("high", "low", "close")),
        _plugin("Supertrend", ("supertrend", "direction"), 11, _supertrend, {"period": 10, "multiplier": 3.0}, inputs=("high", "low", "close")),
        _plugin("Donchian", ("upper", "middle", "lower"), 20, _donchian, {"period": 20}, inputs=("high", "low")),
        _plugin("Ichimoku", ("conversion", "base", "span_a", "span_b"), 78, _ichimoku, {"conversion": 9, "base": 26, "span_b": 52}, inputs=("high", "low")),
        _plugin("CCI", ("cci",), 20, _cci, {"period": 20}, inputs=("high", "low", "close"), pane="oscillator"),
        _plugin("MFI", ("mfi",), 15, _mfi, {"period": 14}, inputs=("high", "low", "close", "volume"), pane="oscillator", normalization="0_100"),
        _plugin("ROC", ("roc",), 13, _roc, {"period": 12}, pane="oscillator", normalization="percent"),
        _plugin("OBV", ("obv",), 2, _obv, {}, inputs=("close", "volume"), pane="volume"),
        _plugin("CMF", ("cmf",), 20, _cmf, {"period": 20}, inputs=("high", "low", "close", "volume"), pane="oscillator"),
        _plugin("Relative Volume", ("relative_volume",), 21, _relative_volume, {"period": 20}, inputs=("volume",), pane="volume", normalization="ratio"),
        _plugin("Volume Profile Approximation", ("point_of_control",), 20, _volume_profile, {"bins": 20}, inputs=("high", "low", "close", "volume")),
        _plugin("Z Score", ("zscore",), 20, _zscore, {"period": 20}, pane="oscillator", normalization="zscore"),
        _plugin("Realized Volatility", ("realized_volatility",), 21, _realized_volatility, {"period": 20, "annualization": 252}, pane="oscillator", normalization="percent"),
        _plugin("Parkinson Volatility", ("parkinson_volatility",), 20, _parkinson, {"period": 20, "annualization": 252}, inputs=("high", "low"), pane="oscillator", normalization="percent"),
        _plugin("Regression Slope", ("regression_slope",), 20, _regression_slope, {"period": 20}, pane="oscillator"),
        _plugin("Correlation Beta", ("correlation", "beta"), 31, _correlation_beta, {"period": 30, "benchmark_close": None}, pane="oscillator"),
        _plugin("Breadth", ("advance_decline", "breadth_percent"), 2, _breadth, {"advances": None, "declines": None}, pane="oscillator"),
        _plugin("Options OI Features", ("put_call_ratio", "call_oi_change", "put_oi_change"), 2, _options_oi, {"call_oi": None, "put_oi": None}, pane="oscillator"),
    )
    for plugin in plugins:
        registry.register(plugin)
    return registry


INDICATOR_REGISTRY = build_default_indicator_registry()

