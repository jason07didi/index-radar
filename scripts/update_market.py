import json
import math
import re
from html import unescape
from io import StringIO
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf


# =========================================================
# INDEX RADAR Strategy 4.0
# 理论主轴：估值 -> 行动 -> 定期不定额
# 辅助层：价格位置 / 情绪 / 技术 / 短期历史情境
# =========================================================

DATA_DIR = Path("data")
MARKET_FILE = DATA_DIR / "market.json"
VALUATION_HISTORY_FILE = DATA_DIR / "valuation_history.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

US_INDICES = {
    "nasdaq100": {"name": "纳斯达克100", "symbol": "^NDX"},
    "sp500": {"name": "标普500", "symbol": "^GSPC"},
}

SSE_NEWSLETTER_ARCHIVE = "https://english.sse.com.cn/events/newsletter/"
SSE_FALLBACK_LATEST = (
    "https://english.sse.com.cn/news/publications/newsletter/c/10827993/"
    "files/a3a75e0b15654ce7a030a6ea803fb916.html"
)
CHINABOND_CURRENT = (
    "https://yield.chinabond.com.cn/cbweb-cbrc-web/cbrc/showCbrc"
)
FRED_DGS10 = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
SP500_PE_HISTORY_URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
NDX_PE_HISTORY_URL = "https://trendonify.com/united-states/stock-market/nasdaq-100/pe-ratio"


# =========================================================
# 通用工具
# =========================================================

def now_shanghai():
    return datetime.now(
        ZoneInfo("Asia/Shanghai")
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def clamp(value, low=0, high=100):
    return max(
        low,
        min(
            high,
            value
        )
    )


def round_or_none(value, digits=2):
    if value is None or pd.isna(value):
        return None

    return round(
        float(value),
        digits
    )


def clean_html(value):
    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S
    )

    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


def extract_number(text):
    if text is None:
        return None

    match = re.search(
        r"[-+]?\d[\d,]*(?:\.\d+)?",
        str(text)
    )

    if not match:
        return None

    try:
        return float(
            match.group(0).replace(",", "")
        )

    except Exception:
        return None


def parse_date(text):
    try:
        value = pd.to_datetime(
            text,
            errors="coerce"
        )

        if pd.isna(value):
            return None

        return value.strftime(
            "%Y-%m-%d"
        )

    except Exception:
        return None


def month_key(date_text):
    try:
        value = pd.to_datetime(
            date_text,
            errors="coerce"
        )

        if pd.isna(value):
            return None

        return value.strftime(
            "%Y-%m"
        )

    except Exception:
        return None


def request_text(
    url,
    timeout=25
):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout
    )

    response.raise_for_status()

    return response.text


def percentile_rank(
    values,
    current
):
    series = pd.Series(
        values,
        dtype="float64"
    ).dropna()

    if len(series) == 0 or current is None:
        return None

    return round(
        float(
            (
                series <= float(current)
            ).mean()
            * 100
        ),
        1
    )


def safe_quantile(
    values,
    q
):
    series = pd.Series(
        values,
        dtype="float64"
    ).dropna()

    if len(series) == 0:
        return None

    return round(
        float(
            series.quantile(q)
        ),
        4
    )


# =========================================================
# 估值历史持久化
# =========================================================

def load_valuation_history():
    if not VALUATION_HISTORY_FILE.exists():

        return {
            "sse50": [],
            "sp500": [],
            "nasdaq100": []
        }

    try:

        with open(
            VALUATION_HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        for key in [
            "sse50",
            "sp500",
            "nasdaq100"
        ]:
            data.setdefault(
                key,
                []
            )

        return data

    except Exception:

        return {
            "sse50": [],
            "sp500": [],
            "nasdaq100": []
        }


def merge_history(
    existing,
    new_items
):
    merged = {}

    for item in (
        existing + new_items
    ):

        pe = item.get("pe")

        period = (
            item.get("period")
            or month_key(
                item.get("date")
            )
        )

        if period is None or pe is None:
            continue

        try:
            pe = float(pe)

        except Exception:
            continue

        if (
            not math.isfinite(pe)
            or pe <= 0
        ):
            continue

        normalized = dict(item)

        normalized["period"] = period

        normalized["pe"] = round(
            pe,
            4
        )

        old = merged.get(period)

        if old is None:

            merged[period] = normalized

            continue

        # 同月优先：
        # official > secondary > proxy > accumulated

        rank = {
            "official": 4,
            "secondary": 3,
            "proxy": 2,
            "accumulated": 1
        }

        old_rank = rank.get(
            old.get("quality"),
            0
        )

        new_rank = rank.get(
            normalized.get("quality"),
            0
        )

        if new_rank >= old_rank:
            merged[period] = normalized

    result = list(
        merged.values()
    )

    result.sort(
        key=lambda x:
        x["period"]
    )

    return result


def save_valuation_history(
    history
):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        VALUATION_HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )


def recent_pe_values(
    history,
    years=10
):
    if not history:
        return []

    rows = []

    for item in history:

        period = item.get(
            "period"
        )

        pe = item.get(
            "pe"
        )

        if period is None or pe is None:
            continue

        date = pd.to_datetime(
            period + "-01",
            errors="coerce"
        )

        if pd.isna(date):
            continue

        rows.append(
            (
                date,
                float(pe)
            )
        )

    if not rows:
        return []

    latest = max(
        x[0]
        for x in rows
    )

    cutoff = (
        latest
        - pd.DateOffset(
            years=years
        )
    )

    selected = [
        pe
        for date, pe in rows
        if date >= cutoff
    ]

    # 若近10年样本太少，
    # 则使用全部可比历史

    if len(selected) < 12:

        selected = [
            pe
            for _, pe in rows
        ]

    return selected


# =========================================================
# 估值数据源：SSE 50 官方月报
# =========================================================

def extract_sse50_from_newsletter(
    html,
    source_url
):

    text = clean_html(
        html
    )

    # 典型格式：
    # SSE 50 2922.97 -2.22 -3.57 12.00

    match = re.search(
        r"SSE\s*50\s+([\d,.]+)\s+[-+\d,.]+\s+[-+\d,.]+\s+([\d,.]+)",
        text,
        flags=re.I,
    )

    if not match:
        return None

    close = extract_number(
        match.group(1)
    )

    pe = extract_number(
        match.group(2)
    )

    if close is None or pe is None:
        return None

    date_match = re.search(
        r"(?:as of|Source:\s*SSE,\s*Wind,\s*as of)\s+"
        r"([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        text,
        flags=re.I,
    )

    date = (
        parse_date(
            date_match.group(1)
        )
        if date_match
        else None
    )

    if date is None:

        issue_match = re.search(
            r"Newsletter\s*[-–]\s*([A-Za-z]+)\s+(20\d{2})",
            text,
            flags=re.I,
        )

        if issue_match:

            date = parse_date(
                f"{issue_match.group(1)} 1, {issue_match.group(2)}"
            )

    if date is None:

        date = now_shanghai()[:10]

    return {

        "date":
            date,

        "period":
            month_key(date),

        "pe":
            round(
                pe,
                4
            ),

        "close":
            round(
                close,
                4
            ),

        "source":
            "Shanghai Stock Exchange Newsletter",

        "source_url":
            source_url,

        "quality":
            "official",

        "method":
            (
                "PE based on previous year's annual report, "
                "excluding loss-making companies"
            ),
    }


def fetch_sse50_official_history(
    max_pages=36
):

    links = []

    try:

        archive_html = request_text(
            SSE_NEWSLETTER_ARCHIVE
        )

        found = re.findall(
            r'href=["\']([^"\']*newsletter/c/[^"\']+\.html)["\']',
            archive_html,
            flags=re.I,
        )

        for href in found:

            url = urljoin(
                SSE_NEWSLETTER_ARCHIVE,
                href
            )

            if url not in links:
                links.append(url)

    except Exception as e:

        print(
            f"SSE 月报目录抓取失败：{e}"
        )

    if SSE_FALLBACK_LATEST not in links:

        links.insert(
            0,
            SSE_FALLBACK_LATEST
        )

    items = []

    for url in links[:max_pages]:

        try:

            html = request_text(
                url
            )

            item = (
                extract_sse50_from_newsletter(
                    html,
                    url
                )
            )

            if item:
                items.append(item)

        except Exception:
            continue

    return merge_history(
        [],
        items
    )


# =========================================================
# 估值数据源：HTML 两列表格
# =========================================================

def parse_two_column_pe_table(
    url,
    quality,
    source_name
):

    html = request_text(
        url
    )

    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        html,
        flags=re.I | re.S
    )

    items = []

    for row in rows:

        cells = re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>",
            row,
            flags=re.I | re.S
        )

        if len(cells) < 2:
            continue

        date_text = clean_html(
            cells[0]
        )

        value_text = clean_html(
            cells[1]
        )

        date = parse_date(
            date_text
        )

        pe = extract_number(
            value_text
        )

        if (
            date is None
            or pe is None
            or pe <= 0
        ):
            continue

        items.append(
            {
                "date":
                    date,

                "period":
                    month_key(
                        date
                    ),

                "pe":
                    round(
                        pe,
                        4
                    ),

                "source":
                    source_name,

                "source_url":
                    url,

                "quality":
                    quality,
            }
        )

    return merge_history(
        [],
        items
    )


def fetch_sp500_pe_history():

    return parse_two_column_pe_table(
        SP500_PE_HISTORY_URL,
        quality="secondary",
        source_name=(
            "Multpl / Robert Shiller dataset"
        ),
    )


def fetch_ndx_pe_history():

    return parse_two_column_pe_table(
        NDX_PE_HISTORY_URL,
        quality="secondary",
        source_name=(
            "Trendonify Nasdaq-100 PE history"
        ),
    )


# =========================================================
# ETF 估值代理：
# 只作交叉校验，不决定历史分位
# =========================================================

def get_etf_proxy_metrics(
    symbol
):

    result = {

        "symbol":
            symbol,

        "pe_ttm":
            None,

        "dividend_yield_pct":
            None,

        "source":
            "Yahoo Finance ETF proxy",

        "quality":
            "proxy",
    }

    try:

        info = (
            yf.Ticker(
                symbol
            ).info
            or {}
        )

        pe = info.get(
            "trailingPE"
        )

        yield_value = info.get(
            "yield"
        )

        if (
            pe is not None
            and math.isfinite(
                float(pe)
            )
        ):

            result[
                "pe_ttm"
            ] = round(
                float(pe),
                2
            )

        if (
            yield_value is not None
            and math.isfinite(
                float(
                    yield_value
                )
            )
        ):

            # Yahoo 通常返回小数形式，
            # 例如 0.0101 = 1.01%

            y = float(
                yield_value
            )

            result[
                "dividend_yield_pct"
            ] = round(
                (
                    y * 100
                    if y < 1
                    else y
                ),
                2
            )

    except Exception as e:

        result[
            "error"
        ] = str(e)

    return result


# =========================================================
# 无风险利率
# =========================================================

def get_china_10y_context():

    html = request_text(
        CHINABOND_CURRENT
    )

    text = clean_html(
        html
    )

    match = re.search(
        r"ChinaBond Government Bond Yield Curve\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        text,
        flags=re.I,
    )

    if not match:

        # 中文页面兼容

        match = re.search(
            r"中债国债收益率曲线\s+"
            r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
            r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
            text,
            flags=re.I,
        )

    if not match:

        raise ValueError(
            "无法解析中国10年期国债收益率"
        )

    values = [
        float(x)
        for x in match.groups()
    ]

    ten_year = values[6]

    date_match = re.search(
        r"(20\d{2}-\d{2}-\d{2})\s*\(%\)",
        text
    )

    date = (
        date_match.group(1)
        if date_match
        else now_shanghai()[:10]
    )

    return {

        "name":
            "中国10年期国债收益率",

        "date":
            date,

        "yield_pct":
            round(
                ten_year,
                4
            ),

        "source":
            "ChinaBond / CCDC",

        "quality":
            "official",
    }


def get_us10y_context():

    response = requests.get(
        FRED_DGS10,
        headers=HEADERS,
        timeout=25
    )

    response.raise_for_status()

    df = pd.read_csv(
        StringIO(
            response.text
        )
    )

    value_col = "DGS10"

    if value_col not in df.columns:

        raise ValueError(
            "FRED DGS10列不存在"
        )

    df[value_col] = pd.to_numeric(
        df[value_col],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            value_col
        ]
    )

    if len(df) < 22:

        raise ValueError(
            "FRED DGS10历史数据不足"
        )

    current = float(
        df.iloc[-1][
            value_col
        ]
    )

    previous = float(
        df.iloc[-2][
            value_col
        ]
    )

    twenty_days_ago = float(
        df.iloc[-21][
            value_col
        ]
    )

    change20 = (
        current
        - twenty_days_ago
    ) * 100

    if change20 >= 25:

        trend = "明显上行"

    elif change20 >= 10:

        trend = "温和上行"

    elif change20 <= -25:

        trend = "明显下行"

    elif change20 <= -10:

        trend = "温和下行"

    else:

        trend = "基本稳定"

    return {

        "name":
            "美国10年期国债收益率",

        "symbol":
            "DGS10",

        "date":
            str(
                df.iloc[-1][
                    df.columns[0]
                ]
            ),

        "yield_pct":
            round(
                current,
                3
            ),

        "daily_change_bp":
            round(
                (
                    current
                    - previous
                )
                * 100,
                1
            ),

        "change_20d_bp":
            round(
                change20,
                1
            ),

        "trend_20d":
            trend,

        "source":
            "FRED / Federal Reserve H.15",

        "quality":
            "official",
    }


# =========================================================
# 市场技术指标
# =========================================================

def calculate_indicators(
    df
):

    df = (
        df.copy()
        .sort_index()
    )

    close = df[
        "Close"
    ]

    high = df[
        "High"
    ]

    low = df[
        "Low"
    ]


    df["MA5"] = (
        close
        .rolling(5)
        .mean()
    )

    df["MA20"] = (
        close
        .rolling(20)
        .mean()
    )

    df["MA60"] = (
        close
        .rolling(60)
        .mean()
    )

    df["MA200"] = (
        close
        .rolling(200)
        .mean()
    )


    boll_mid = (
        close
        .rolling(20)
        .mean()
    )

    boll_std = (
        close
        .rolling(20)
        .std(ddof=0)
    )

    df[
        "BOLL_MID"
    ] = boll_mid

    df[
        "BOLL_UPPER"
    ] = (
        boll_mid
        + 2 * boll_std
    )

    df[
        "BOLL_LOWER"
    ] = (
        boll_mid
        - 2 * boll_std
    )


    delta = close.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = (
        avg_gain
        / avg_loss
    )

    df["RSI14"] = (
        100
        - 100
        / (
            1 + rs
        )
    )


    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    df["DIF"] = (
        ema12
        - ema26
    )

    df["DEA"] = (
        df["DIF"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        2
        * (
            df["DIF"]
            - df["DEA"]
        )
    )


    df["RET20"] = (
        close
        .pct_change(20)
        * 100
    )

    df["RET60"] = (
        close
        .pct_change(60)
        * 100
    )


    daily_return = (
        close
        .pct_change()
    )

    df["VOL20"] = (
        daily_return
        .rolling(20)
        .std(ddof=0)
        * math.sqrt(252)
        * 100
    )


    df["HIGH20"] = (
        high
        .rolling(20)
        .max()
    )

    df["LOW20"] = (
        low
        .rolling(20)
        .min()
    )

    df["HIGH252"] = (
        high
        .rolling(
            252,
            min_periods=200
        )
        .max()
    )

    df["LOW252"] = (
        low
        .rolling(
            252,
            min_periods=200
        )
        .min()
    )


    df["DRAWDOWN_52W"] = (
        (
            close
            / df["HIGH252"]
        )
        - 1
    ) * 100

    df["DEV_MA20"] = (
        (
            close
            / df["MA20"]
        )
        - 1
    ) * 100

    df["DEV_MA60"] = (
        (
            close
            / df["MA60"]
        )
        - 1
    ) * 100

    df["DEV_MA200"] = (
        (
            close
            / df["MA200"]
        )
        - 1
    ) * 100

    df["MACD_NORM"] = (
        df["MACD"]
        / close
        * 100
    )

    return df


def calculate_volatility_percentile_3y(
    df
):

    values = (
        df["VOL20"]
        .dropna()
        .tail(756)
    )

    if len(values) < 60:
        return None

    current = float(
        values.iloc[-1]
    )

    return round(
        float(
            (
                values <= current
            ).mean()
            * 100
        ),
        1
    )


# =========================================================
# 价格位置：
# 只使用长期价格变量，不冒充估值
# =========================================================

def calculate_price_position(
    latest
):

    drawdown = float(
        latest[
            "DRAWDOWN_52W"
        ]
    )

    dev200 = float(
        latest[
            "DEV_MA200"
        ]
    )

    score = 50

    reasons = []


    if drawdown >= -3:

        score -= 15

        reasons.append(
            "价格接近52周高位"
        )

    elif drawdown >= -8:

        score -= 7

        reasons.append(
            "价格距离52周高位较近"
        )

    elif drawdown >= -15:

        score += 4

        reasons.append(
            "价格出现一定回撤"
        )

    elif drawdown >= -25:

        score += 13

        reasons.append(
            "价格处于中等回撤区间"
        )

    elif drawdown >= -35:

        score += 21

        reasons.append(
            "价格处于较深回撤区间"
        )

    else:

        score += 27

        reasons.append(
            "价格处于极深回撤区间"
        )


    if dev200 > 20:

        score -= 22

        reasons.append(
            "价格显著高于MA200"
        )

    elif dev200 > 10:

        score -= 13

        reasons.append(
            "价格明显高于MA200"
        )

    elif dev200 > 3:

        score -= 5

        reasons.append(
            "价格温和高于MA200"
        )

    elif dev200 >= -5:

        score += 1

        reasons.append(
            "价格位于MA200附近"
        )

    elif dev200 >= -15:

        score += 10

        reasons.append(
            "价格低于MA200"
        )

    elif dev200 >= -25:

        score += 18

        reasons.append(
            "价格明显低于MA200"
        )

    else:

        score += 24

        reasons.append(
            "价格大幅低于MA200"
        )


    score = int(
        round(
            clamp(
                score
            )
        )
    )


    if score >= 80:

        state = "深度回撤"

    elif score >= 65:

        state = "价格偏低"

    elif score >= 45:

        state = "价格中性"

    elif score >= 30:

        state = "价格偏高"

    else:

        state = "价格明显偏高"


    return {

        "score":
            score,

        "state":
            state,

        "reasons":
            reasons

    }


def calculate_market_temperature(
    latest
):

    # 仅作为前端兼容字段；
    # 本质是价格位置的反向表述

    position = (
        calculate_price_position(
            latest
        )
    )

    temperature = int(
        round(
            clamp(
                100
                - position["score"]
            )
        )
    )


    if temperature < 25:

        state = "明显偏冷"

    elif temperature < 40:

        state = "偏冷"

    elif temperature <= 60:

        state = "平衡"

    elif temperature < 75:

        state = "偏热"

    else:

        state = "明显过热"


    return {

        "score":
            temperature,

        "state":
            state,

        "meaning":
            (
                "价格温度只描述价格位置，"
                "不参与估值结论。"
            ),
    }


# =========================================================
# 技术状态：
# 只描述执行环境，不决定长期买卖
# =========================================================

def calculate_technical_score(
    latest
):

    close = float(
        latest["Close"]
    )

    ma5 = float(
        latest["MA5"]
    )

    ma20 = float(
        latest["MA20"]
    )

    ma60 = float(
        latest["MA60"]
    )

    rsi = float(
        latest["RSI14"]
    )

    dif = float(
        latest["DIF"]
    )

    dea = float(
        latest["DEA"]
    )

    macd = float(
        latest["MACD"]
    )


    score = 50

    reasons = []


    if close > ma20:

        score += 8

        reasons.append(
            "指数位于MA20上方"
        )

    else:

        score -= 8

        reasons.append(
            "指数位于MA20下方"
        )


    if close > ma60:

        score += 10

        reasons.append(
            "指数位于MA60上方"
        )

    else:

        score -= 10

        reasons.append(
            "指数位于MA60下方"
        )


    if ma5 > ma20:

        score += 5

    else:

        score -= 5


    if ma20 > ma60:

        score += 7

    else:

        score -= 7


    if dif > dea:

        score += 6

        reasons.append(
            "MACD结构偏强"
        )

    else:

        score -= 6

        reasons.append(
            "MACD结构偏弱"
        )


    score += (
        4
        if macd > 0
        else -4
    )


    if 50 <= rsi <= 70:

        score += 6

        reasons.append(
            "RSI处于偏强但未过热区间"
        )

    elif 40 <= rsi < 50:

        score -= 2

    elif 30 <= rsi < 40:

        score -= 5

    elif rsi < 30:

        score -= 8

        reasons.append(
            "RSI进入超卖区域"
        )

    elif 70 < rsi <= 75:

        score += 2

    elif rsi > 75:

        score -= 4

        reasons.append(
            "RSI处于较高位置"
        )


    score = int(
        round(
            clamp(
                score
            )
        )
    )


    if score >= 80:

        state = "强势"

    elif score >= 65:

        state = "偏强"

    elif score >= 45:

        state = "中性"

    elif score >= 30:

        state = "偏弱"

    else:

        state = "弱势"


    return {

        "score":
            score,

        "state":
            state,

        "reasons":
            reasons

    }


# =========================================================
# VIX / VXN：
# 只表示风险情绪
# =========================================================

def get_volatility_index_context(
    symbol,
    name,
    kind
):

    df = (
        yf.Ticker(
            symbol
        )
        .history(
            period="5y",
            interval="1d",
            auto_adjust=False
        )
    )


    if df.empty:

        raise ValueError(
            f"{name}未返回数据"
        )


    close = (
        df["Close"]
        .dropna()
    )


    if len(close) < 60:

        raise ValueError(
            f"{name}历史数据不足"
        )


    current = float(
        close.iloc[-1]
    )

    previous = float(
        close.iloc[-2]
    )

    percentile = float(
        (
            close <= current
        ).mean()
        * 100
    )


    if kind == "vxn":

        if current < 16:

            state = "低波动"
            sentiment_score = 85

        elif current < 20:

            state = "较低波动"
            sentiment_score = 70

        elif current < 25:

            state = "正常"
            sentiment_score = 55

        elif current < 30:

            state = "偏高波动"
            sentiment_score = 40

        elif current < 40:

            state = "高波动"
            sentiment_score = 25

        else:

            state = "极端波动"
            sentiment_score = 10


    else:

        if current < 13:

            state = "低波动"
            sentiment_score = 85

        elif current < 16:

            state = "较低波动"
            sentiment_score = 70

        elif current < 20:

            state = "正常"
            sentiment_score = 55

        elif current < 25:

            state = "偏高波动"
            sentiment_score = 40

        elif current < 35:

            state = "高波动"
            sentiment_score = 25

        else:

            state = "极端波动"
            sentiment_score = 10


    return {

        "name":
            name,

        "symbol":
            symbol,

        "date":
            close.index[-1]
            .strftime(
                "%Y-%m-%d"
            ),

        "value":
            round(
                current,
                2
            ),

        "change":
            round(
                current
                - previous,
                2
            ),

        "change_pct":
            round(
                (
                    current
                    / previous
                    - 1
                )
                * 100,
                2
            ),

        "percentile_5y":
            round(
                percentile,
                1
            ),

        "state":
            state,

        "sentiment_score":
            sentiment_score,

        "source":
            "Yahoo Finance / Cboe index",
    }


def get_macro_context():

    macro = {

        "updated_at":
            now_shanghai()

    }


    try:

        macro["vix"] = (
            get_volatility_index_context(
                "^VIX",
                "Cboe VIX",
                "vix"
            )
        )

    except Exception as e:

        macro["vix"] = {

            "name":
                "Cboe VIX",

            "symbol":
                "^VIX",

            "error":
                str(e)
        }


    try:

        macro["vxn"] = (
            get_volatility_index_context(
                "^VXN",
                "Cboe Nasdaq-100 Volatility Index",
                "vxn"
            )
        )

    except Exception as e:

        macro["vxn"] = {

            "name":
                "Cboe Nasdaq-100 Volatility Index",

            "symbol":
                "^VXN",

            "error":
                str(e)
        }


    try:

        macro["us10y"] = (
            get_us10y_context()
        )

    except Exception as e:

        macro["us10y"] = {

            "name":
                "美国10年期国债收益率",

            "symbol":
                "DGS10",

            "error":
                str(e)
        }


    try:

        macro["china10y"] = (
            get_china_10y_context()
        )

    except Exception as e:

        macro["china10y"] = {

            "name":
                "中国10年期国债收益率",

            "error":
                str(e)
        }


    return macro


# =========================================================
# 指数专属风险情绪
# =========================================================

def human_sentiment(
    score
):

    if score < 25:

        return "明显谨慎"

    if score < 40:

        return "偏谨慎"

    if score <= 60:

        return "平稳"

    if score < 75:

        return "偏积极"

    return "明显亢奋"


def calculate_sse50_risk_state(
    data
):

    ret20 = float(
        data[
            "return20_pct"
        ]
    )

    vol_pct = data.get(
        "volatility_percentile_3y"
    )

    score = 50

    components = []


    if ret20 >= 8:

        score += 12

        components.append(
            f"近20日上涨{ret20:.1f}%"
        )

    elif ret20 >= 3:

        score += 6

        components.append(
            f"近20日温和上涨{ret20:.1f}%"
        )

    elif ret20 <= -8:

        score -= 12

        components.append(
            f"近20日下跌{abs(ret20):.1f}%"
        )

    elif ret20 <= -3:

        score -= 6

        components.append(
            f"近20日温和下跌{abs(ret20):.1f}%"
        )

    else:

        components.append(
            "近20日价格变化有限"
        )


    if vol_pct is not None:

        if (
            vol_pct >= 80
            and ret20 < 0
        ):

            score -= 12

            components.append(
                (
                    f"波动率位于近3年约{vol_pct:.0f}%分位，"
                    "且价格下跌"
                )
            )

        elif (
            vol_pct >= 80
            and ret20 >= 0
        ):

            score += 4

            components.append(
                (
                    f"波动率位于近3年约{vol_pct:.0f}%分位，"
                    "交易活跃"
                )
            )

        elif vol_pct <= 20:

            score += 2

            components.append(
                (
                    f"波动率位于近3年约{vol_pct:.0f}%分位，"
                    "市场较平静"
                )
            )


    score = int(
        round(
            clamp(
                score
            )
        )
    )


    return {

        "label":
            "A股市场风险状态",

        "score":
            score,

        "state":
            human_sentiment(
                score
            ),

        "confidence":
            "中等",

        "method":
            "近20日动量 + 20日波动率历史分位",

        "primary_indicator": {

            "name":
                "风险状态综合",

            "value":
                score,

            "unit":
                "分"

        },

        "components":
            components,

        "summary":
            (
                "该模块只描述短期风险偏好，"
                "不参与估值和定投决策。"
            ),

        "note":
            (
                "上证50暂无与VIX/VXN完全对应的单一官方情绪指标，"
                "因此使用价格动量与波动状态描述风险环境。"
            ),
    }


def calculate_us_sentiment(
    index_key,
    macro
):

    item = macro.get(
        (
            "vxn"
            if index_key == "nasdaq100"
            else "vix"
        ),
        {}
    )


    if (
        not item
        or item.get("error")
    ):

        return {

            "label":
                (
                    "科技股风险情绪"
                    if index_key == "nasdaq100"
                    else "美股风险情绪"
                ),

            "score":
                50,

            "state":
                "数据不足",

            "confidence":
                "较低",

            "method":
                (
                    "VXN"
                    if index_key == "nasdaq100"
                    else "VIX"
                ),

            "primary_indicator": {

                "name":
                    (
                        "VXN"
                        if index_key == "nasdaq100"
                        else "VIX"
                    ),

                "value":
                    None
            },

            "components":
                [],

            "summary":
                (
                    "波动率指数暂不可用，"
                    "不参与任何长期决策。"
                ),

            "note":
                "市场情绪仅作辅助观察。",
        }


    score = int(
        item[
            "sentiment_score"
        ]
    )


    label = (
        "科技股风险情绪"
        if index_key == "nasdaq100"
        else "美股风险情绪"
    )


    primary_name = (
        "VXN"
        if index_key == "nasdaq100"
        else "VIX"
    )


    return {

        "label":
            label,

        "score":
            score,

        "state":
            human_sentiment(
                score
            ),

        "confidence":
            "较高",

        "method":
            primary_name,

        "primary_indicator": {

            "name":
                primary_name,

            "value":
                item.get("value"),

            "unit":
                "",

            "state":
                item.get("state"),

            "percentile_5y":
                item.get(
                    "percentile_5y"
                ),
        },

        "components": [

            f"{primary_name} 当前为 {item.get('value')}",

            f"5年历史分位约 {item.get('percentile_5y')}%",

        ],

        "summary":
            (
                "该指标反映风险偏好与波动预期，"
                "只用于描述市场环境，"
                "不参与估值或定投金额。"
            ),

        "note":
            (
                "美国10年期国债已从情绪模型中移出，"
                "归入利率与估值环境。"
            ),
    }


# =========================================================
# 估值引擎
# =========================================================

def valuation_band_from_pe_percentile(
    percentile
):

    if percentile is None:

        return "数据不足"

    if percentile <= 20:

        return "明显低估"

    if percentile <= 40:

        return "低估"

    if percentile <= 60:

        return "合理"

    if percentile <= 80:

        return "偏高估"

    return "明显高估"


def action_from_valuation_state(
    state
):

    mapping = {

        "明显低估":
            "增强定投",

        "低估":
            "继续定投",

        "合理":
            "持有，暂停新增",

        "偏高估":
            "持有，暂停新增",

        "明显高估":
            "高仓位可分批再平衡",

        "PE异常/需辅助估值":
            "暂不依据PE单独决策",

        "数据不足":
            "估值数据不足，暂不判断",
    }

    return mapping.get(
        state,
        "估值数据不足，暂不判断"
    )


def build_valuation_model(
    index_key,
    current_pe,
    history,
    method_name,
    primary_method,
    source,
    source_quality,
    risk_free=None,
    dividend_yield_pct=None,
    proxy_pe=None,
    notes=None,
):

    pe_values = recent_pe_values(
        history,
        years=10
    )


    percentile = (
        percentile_rank(
            pe_values,
            current_pe
        )
        if current_pe
        else None
    )


    q20 = safe_quantile(
        pe_values,
        0.20
    )

    q40 = safe_quantile(
        pe_values,
        0.40
    )

    q60 = safe_quantile(
        pe_values,
        0.60
    )

    q80 = safe_quantile(
        pe_values,
        0.80
    )


    state = (
        valuation_band_from_pe_percentile(
            percentile
        )
    )


    # 标普在盈利崩塌期PE可能失真，
    # 极端PE时不让单一PE直接触发卖出

    pe_reliability = "正常"

    if (
        index_key == "sp500"
        and current_pe is not None
        and current_pe >= 50
    ):

        pe_reliability = (
            "较低，需要PB或正常化盈利辅助"
        )

        state = (
            "PE异常/需辅助估值"
        )


    action = (
        action_from_valuation_state(
            state
        )
    )


    earnings_yield = (
        100 / current_pe
        if (
            current_pe
            and current_pe > 0
        )
        else None
    )


    risk_free_yield = None

    ey_to_bond = None

    ey_minus_bond = None


    if (
        risk_free
        and not risk_free.get(
            "error"
        )
    ):

        risk_free_yield = (
            risk_free.get(
                "yield_pct"
            )
        )

        if (
            earnings_yield is not None
            and risk_free_yield
            not in (
                None,
                0
            )
        ):

            ey_to_bond = (
                earnings_yield
                / risk_free_yield
            )

            ey_minus_bond = (
                earnings_yield
                - risk_free_yield
            )


    entry_pe = q40

    entry_ey = (
        100 / entry_pe
        if (
            entry_pe
            and entry_pe > 0
        )
        else None
    )


    if percentile is None:

        attractiveness_score = None

    else:

        attractiveness_score = int(
            round(
                100
                - percentile
            )
        )


    reasons = []


    if current_pe is not None:

        reasons.append(
            (
                "当前可比口径PE约为 "
                f"{current_pe:.2f}"
            )
        )


    if percentile is not None:

        reasons.append(
            (
                "当前PE位于近10年/可用历史约 "
                f"{percentile:.1f}% 分位"
            )
        )


    if earnings_yield is not None:

        reasons.append(
            (
                "对应盈利收益率约 "
                f"{earnings_yield:.2f}%"
            )
        )


    if risk_free_yield is not None:

        reasons.append(
            (
                "10年期国债收益率约 "
                f"{risk_free_yield:.2f}%"
            )
        )


    if ey_to_bond is not None:

        reasons.append(
            (
                "盈利收益率约为10年国债收益率的 "
                f"{ey_to_bond:.2f} 倍"
            )
        )


    if dividend_yield_pct is not None:

        reasons.append(
            (
                "ETF代理股息率约 "
                f"{dividend_yield_pct:.2f}%"
            )
        )


    history_count = len(
        pe_values
    )


    if (
        source_quality == "official"
        and history_count >= 24
    ):

        confidence = "较高"

    elif history_count >= 24:

        confidence = "中等"

    elif history_count >= 6:

        confidence = "中等偏低"

    else:

        confidence = "较低"


    formula_type = (
        "earnings_yield"
        if primary_method == "earnings_yield"
        else "pe"
    )


    return {

        "method_name":
            method_name,

        "primary_method":
            primary_method,

        "state":
            state,

        "action":
            action,

        "core_decision_enabled":
            (
                percentile is not None
                and history_count >= 6
            ),

        "confidence":
            confidence,

        "pe_reliability":
            pe_reliability,

        "pe":
            round_or_none(
                current_pe,
                2
            ),

        "pe_percentile_10y":
            percentile,

        "earnings_yield_pct":
            round_or_none(
                earnings_yield,
                2
            ),

        "dividend_yield_pct":
            round_or_none(
                dividend_yield_pct,
                2
            ),

        "risk_free_yield_pct":
            round_or_none(
                risk_free_yield,
                3
            ),

        "earnings_yield_to_bond":
            round_or_none(
                ey_to_bond,
                2
            ),

        "earnings_yield_minus_bond_pct":
            round_or_none(
                ey_minus_bond,
                2
            ),

        "attractiveness_score_compat":
            attractiveness_score,

        "history_count":
            history_count,

        "history_window":
            (
                "近10年；样本不足时使用全部可比历史"
            ),

        "pe_band": {

            "p20":
                q20,

            "p40":
                q40,

            "p60":
                q60,

            "p80":
                q80,
        },

        "investment_formula": {

            "type":
                formula_type,

            "entry_pe":
                round_or_none(
                    entry_pe,
                    4
                ),

            "entry_earnings_yield_pct":
                round_or_none(
                    entry_ey,
                    4
                ),

            "description":
                (
                    "低估区内按PDF的定期不定额思想计算："
                    "盈利收益率法使用 (当前EY/低估阈值EY)^n；"
                    "博格PE法使用 (低估阈值PE/当前PE)^n。"
                ),

            "active_only_when_undervalued":
                True,
        },

        "source":
            source,

        "source_quality":
            source_quality,

        "proxy_pe":
            round_or_none(
                proxy_pe,
                2
            ),

        "reasons":
            reasons,

        "notes":
            notes or [],

        "decision_rule":
            (
                "估值决定定投/持有/再平衡；"
                "价格、情绪、技术和20日情境不改变核心估值结论。"
            ),
    }


def build_sse50_valuation(
    market_data,
    history_store,
    macro
):

    official_items = []

    try:

        official_items = (
            fetch_sse50_official_history()
        )

    except Exception as e:

        print(
            f"SSE50估值历史抓取失败：{e}"
        )


    history_store[
        "sse50"
    ] = merge_history(
        history_store.get(
            "sse50",
            []
        ),
        official_items
    )


    history = history_store[
        "sse50"
    ]


    latest_official = None


    if history:

        candidates = [
            x
            for x in history
            if x.get("close") is not None
        ]

        if candidates:

            latest_official = sorted(
                candidates,
                key=lambda x:
                x["period"]
            )[-1]


    current_pe = None

    source = (
        "SSE official newsletter"
    )


    notes = [

        (
            "SSE官方月报PE基于上一年度年报并剔除亏损公司，"
            "不等同于严格PE-TTM。"
        ),

        (
            "若当前指数价格晚于最新月报，"
            "则仅按价格变化对官方月末PE做近似更新，"
            "盈利分母保持不变。"
        ),
    ]


    if latest_official:

        official_pe = float(
            latest_official[
                "pe"
            ]
        )

        official_close = float(
            latest_official[
                "close"
            ]
        )

        current_close = float(
            market_data[
                "close"
            ]
        )


        if official_close > 0:

            current_pe = (
                official_pe
                * current_close
                / official_close
            )

        else:

            current_pe = (
                official_pe
            )


        source = (
            latest_official.get(
                "source",
                source
            )
        )


    china10y = macro.get(
        "china10y"
    )


    return build_valuation_model(
        index_key="sse50",
        current_pe=current_pe,
        history=history,
        method_name=(
            "盈利收益率法（现代化版本）"
        ),
        primary_method="earnings_yield",
        source=source,
        source_quality="official",
        risk_free=china10y,
        dividend_yield_pct=None,
        proxy_pe=None,
        notes=notes,
    )


def build_sp500_valuation(
    history_store,
    macro
):

    fresh = []


    try:

        fresh = (
            fetch_sp500_pe_history()
        )

    except Exception as e:

        print(
            f"S&P500 PE历史抓取失败：{e}"
        )


    history_store[
        "sp500"
    ] = merge_history(
        history_store.get(
            "sp500",
            []
        ),
        fresh
    )


    history = history_store[
        "sp500"
    ]


    current_pe = None


    if history:

        current_pe = float(
            sorted(
                history,
                key=lambda x:
                x["period"]
            )[-1]["pe"]
        )


    proxy = (
        get_etf_proxy_metrics(
            "SPY"
        )
    )


    if (
        current_pe is None
        and proxy.get("pe_ttm")
    ):

        current_pe = proxy[
            "pe_ttm"
        ]


        history_store[
            "sp500"
        ] = merge_history(
            history,
            [
                {
                    "date":
                        now_shanghai()[:10],

                    "period":
                        month_key(
                            now_shanghai()[:10]
                        ),

                    "pe":
                        current_pe,

                    "source":
                        "Yahoo Finance SPY PE proxy",

                    "quality":
                        "proxy",
                }
            ],
        )


        history = history_store[
            "sp500"
        ]


    return build_valuation_model(
        index_key="sp500",
        current_pe=current_pe,
        history=history,
        method_name=(
            "博格公式框架（PE历史位置 + 股息率；盈利增长待自动化接入）"
        ),
        primary_method="bogle_pe",
        source=(
            "Multpl / Robert Shiller dataset; "
            "SPY used as cross-check"
        ),
        source_quality="secondary",
        risk_free=macro.get(
            "us10y"
        ),
        dividend_yield_pct=proxy.get(
            "dividend_yield_pct"
        ),
        proxy_pe=proxy.get(
            "pe_ttm"
        ),
        notes=[
            (
                "当前PE历史序列使用Multpl所列TTM "
                "as-reported earnings口径；"
                "SPY PE仅用于交叉校验，不混入历史分位。"
            ),
            (
                "博格框架中的盈利增长仍应作为基本面解释变量；"
                "本版尚未自动化接入，因此不伪造增长预测。"
            ),
            (
                "若PE因盈利骤降出现异常高值，"
                "系统将降低PE单一指标的决策权，"
                "后续应接入PB/正常化盈利。"
            ),
        ],
    )


def build_ndx_valuation(
    history_store,
    macro
):

    fresh = []


    try:

        fresh = (
            fetch_ndx_pe_history()
        )

    except Exception as e:

        print(
            f"Nasdaq100 PE历史抓取失败：{e}"
        )


    history_store[
        "nasdaq100"
    ] = merge_history(
        history_store.get(
            "nasdaq100",
            []
        ),
        fresh
    )


    history = history_store[
        "nasdaq100"
    ]


    current_pe = None


    if history:

        current_pe = float(
            sorted(
                history,
                key=lambda x:
                x["period"]
            )[-1]["pe"]
        )


    proxy = (
        get_etf_proxy_metrics(
            "QQQ"
        )
    )


    if (
        current_pe is None
        and proxy.get("pe_ttm")
    ):

        current_pe = proxy[
            "pe_ttm"
        ]


        history_store[
            "nasdaq100"
        ] = merge_history(
            history,
            [
                {
                    "date":
                        now_shanghai()[:10],

                    "period":
                        month_key(
                            now_shanghai()[:10]
                        ),

                    "pe":
                        current_pe,

                    "source":
                        "Yahoo Finance QQQ PE proxy",

                    "quality":
                        "proxy",
                }
            ],
        )


        history = history_store[
            "nasdaq100"
        ]


    return build_valuation_model(
        index_key="nasdaq100",
        current_pe=current_pe,
        history=history,
        method_name=(
            "成长型博格框架（PE自身历史位置为核心；"
            "盈利增长待自动化接入）"
        ),
        primary_method="bogle_pe",
        source=(
            "Trendonify Nasdaq-100 PE history; "
            "QQQ used as cross-check"
        ),
        source_quality="secondary",
        risk_free=macro.get(
            "us10y"
        ),
        dividend_yield_pct=proxy.get(
            "dividend_yield_pct"
        ),
        proxy_pe=proxy.get(
            "pe_ttm"
        ),
        notes=[
            (
                "纳斯达克100按成长型指数框架处理，"
                "核心比较自身历史PE，"
                "而不是与上证50做横向绝对PE比较。"
            ),
            (
                "QQQ PE与股息率只作为可投资ETF代理数据和交叉校验。"
            ),
            (
                "盈利增长是成长型博格框架的重要组成部分，"
                "但本版不使用静态或过时增长率去直接驱动买卖结论。"
            ),
        ],
    )


# =========================================================
# 历史相似情境：
# 仅短期观察，不参与策略
# =========================================================

def build_path_label(
    up_pct,
    sideways_pct,
    down_pct
):

    if (
        up_pct >= 45
        and up_pct >= down_pct + 10
    ):

        return "偏强上行"


    if (
        down_pct >= 45
        and down_pct >= up_pct + 10
    ):

        return "偏弱下行"


    if sideways_pct >= 40:

        if up_pct >= down_pct + 8:

            return "震荡偏强"

        if down_pct >= up_pct + 8:

            return "震荡偏弱"

        return "震荡整理"


    if up_pct > down_pct:

        return "震荡偏强"


    if down_pct > up_pct:

        return "震荡偏弱"


    return "震荡整理"


def calculate_historical_scenarios(
    df,
    horizon=20,
    max_samples=120,
    direction_threshold=3.0
):

    current = (
        df.iloc[-1]
    )


    required = [
        "DEV_MA20",
        "DEV_MA60",
        "DEV_MA200",
        "RSI14",
        "DRAWDOWN_52W",
        "RET20",
        "MACD_NORM",
    ]


    if any(
        pd.isna(
            current[x]
        )
        for x in required
    ):

        return None


    current_features = {

        x:
            float(
                current[x]
            )

        for x in required

    }


    scales = {

        "DEV_MA20":
            6.0,

        "DEV_MA60":
            10.0,

        "DEV_MA200":
            15.0,

        "RSI14":
            15.0,

        "DRAWDOWN_52W":
            12.0,

        "RET20":
            10.0,

        "MACD_NORM":
            0.6,
    }


    candidates = []

    start_index = 252

    end_index = (
        len(df)
        - horizon
        - 1
    )


    if end_index <= start_index:

        return None


    for i in range(
        start_index,
        end_index,
        3
    ):

        row = (
            df.iloc[i]
        )

        parts = []

        valid = True


        for feature in required:

            value = row[
                feature
            ]


            if pd.isna(value):

                valid = False

                break


            difference = (

                float(value)

                -

                current_features[
                    feature
                ]

            ) / scales[
                feature
            ]


            parts.append(
                difference ** 2
            )


        if valid:

            candidates.append(
                {
                    "index":
                        i,

                    "distance":
                        math.sqrt(
                            sum(parts)
                            / len(parts)
                        )
                }
            )


    if len(candidates) < 30:

        return None


    selected = sorted(
        candidates,
        key=lambda x:
            x["distance"]
    )[
        :
        min(
            max_samples,
            len(candidates)
        )
    ]


    total_weight = 0.0

    sum_weight_squared = 0.0

    up_weight = 0.0

    sideways_weight = 0.0

    down_weight = 0.0

    above_ma20_weight = 0.0

    above_ma60_weight = 0.0

    break_low20_weight = 0.0

    break_high20_weight = 0.0

    weighted_return_sum = 0.0

    future_returns = []

    selected_distances = []


    for candidate in selected:

        i = candidate[
            "index"
        ]

        distance = candidate[
            "distance"
        ]


        weight = math.exp(
            -0.55
            * distance
        )


        future = df.iloc[
            i + 1:
            i + horizon + 1
        ]


        if len(future) < horizon:
            continue


        current_row = (
            df.iloc[i]
        )


        start_close = float(
            current_row[
                "Close"
            ]
        )


        end_close = float(
            future.iloc[-1][
                "Close"
            ]
        )


        future_return = (

            (
                end_close
                / start_close
            )

            - 1

        ) * 100


        total_weight += (
            weight
        )

        sum_weight_squared += (
            weight ** 2
        )

        weighted_return_sum += (
            future_return
            * weight
        )


        future_returns.append(
            future_return
        )

        selected_distances.append(
            distance
        )


        if future_return > direction_threshold:

            up_weight += (
                weight
            )

        elif future_return < -direction_threshold:

            down_weight += (
                weight
            )

        else:

            sideways_weight += (
                weight
            )


        if (
            future[
                "Close"
            ]
            > float(
                current_row[
                    "MA20"
                ]
            )
        ).any():

            above_ma20_weight += (
                weight
            )


        if (
            future[
                "Close"
            ]
            > float(
                current_row[
                    "MA60"
                ]
            )
        ).any():

            above_ma60_weight += (
                weight
            )


        if float(
            future[
                "Low"
            ].min()
        ) < float(
            current_row[
                "LOW20"
            ]
        ):

            break_low20_weight += (
                weight
            )


        if float(
            future[
                "High"
            ].max()
        ) > float(
            current_row[
                "HIGH20"
            ]
        ):

            break_high20_weight += (
                weight
            )


    if total_weight <= 0:

        return None


    def pct(weight):

        return int(
            round(
                weight
                / total_weight
                * 100
            )
        )


    up_pct = pct(
        up_weight
    )

    down_pct = pct(
        down_weight
    )

    sideways_pct = max(
        0,
        100
        - up_pct
        - down_pct
    )


    avg_return = (
        weighted_return_sum
        / total_weight
    )


    median_return = float(
        pd.Series(
            future_returns
        ).median()
    )


    avg_distance = (
        sum(
            selected_distances
        )
        / len(
            selected_distances
        )
    )


    ess = (
        total_weight ** 2
        / sum_weight_squared
        if sum_weight_squared > 0
        else 0
    )


    if (
        ess >= 60
        and avg_distance <= 1.25
    ):

        confidence = "较高"

    elif (
        ess >= 35
        and avg_distance <= 1.75
    ):

        confidence = "中等"

    else:

        confidence = "较低"


    return {

        "horizon_days":
            horizon,

        "sample_size":
            len(
                future_returns
            ),

        "effective_sample_size":
            round(
                ess,
                1
            ),

        "method":
            "历史相似状态加权频率",

        "confidence":
            confidence,

        "average_distance":
            round(
                avg_distance,
                3
            ),

        "direction_threshold_pct":
            direction_threshold,

        "up_pct":
            up_pct,

        "sideways_pct":
            sideways_pct,

        "down_pct":
            down_pct,

        "path_label":
            build_path_label(
                up_pct,
                sideways_pct,
                down_pct
            ),

        "average_return_pct":
            round(
                avg_return,
                2
            ),

        "median_return_pct":
            round(
                median_return,
                2
            ),

        "events": {

            "above_ma20_pct":
                pct(
                    above_ma20_weight
                ),

            "above_ma60_pct":
                pct(
                    above_ma60_weight
                ),

            "break_low20_pct":
                pct(
                    break_low20_weight
                ),

            "break_high20_pct":
                pct(
                    break_high20_weight
                ),
        },

        "strategy_role":
            "observation_only",

        "note":
            (
                "该模块不参与估值、"
                "定投金额或卖出判断。"
            ),
    }


# =========================================================
# 图表历史
# =========================================================

def build_history(
    df,
    periods=252
):

    history = []


    for index, row in (
        df.tail(
            periods
        ).iterrows()
    ):

        history.append(
            {
                "date":
                    index.strftime(
                        "%Y-%m-%d"
                    ),

                "open":
                    round_or_none(
                        row["Open"]
                    ),

                "high":
                    round_or_none(
                        row["High"]
                    ),

                "low":
                    round_or_none(
                        row["Low"]
                    ),

                "close":
                    round_or_none(
                        row["Close"]
                    ),

                "ma5":
                    round_or_none(
                        row["MA5"]
                    ),

                "ma20":
                    round_or_none(
                        row["MA20"]
                    ),

                "ma60":
                    round_or_none(
                        row["MA60"]
                    ),

                "ma200":
                    round_or_none(
                        row["MA200"]
                    ),

                "boll_upper":
                    round_or_none(
                        row["BOLL_UPPER"]
                    ),

                "boll_mid":
                    round_or_none(
                        row["BOLL_MID"]
                    ),

                "boll_lower":
                    round_or_none(
                        row["BOLL_LOWER"]
                    ),
            }
        )


    return history


# =========================================================
# 行情结果
# =========================================================

def build_result(
    name,
    symbol,
    source,
    df
):

    df = (
        calculate_indicators(
            df
        )
    )


    if len(df) < 320:

        raise ValueError(
            (
                f"{name}"
                "长期历史数据不足320个交易日"
            )
        )


    latest = (
        df.iloc[-1]
    )

    previous = (
        df.iloc[-2]
    )


    required = [
        "MA200",
        "HIGH252",
        "LOW252",
        "DRAWDOWN_52W",
        "DEV_MA200",
        "RET20",
        "RET60",
        "VOL20"
    ]


    for field in required:

        if pd.isna(
            latest[
                field
            ]
        ):

            raise ValueError(
                (
                    f"{name}"
                    f"无法计算长期指标 {field}"
                )
            )


    close = float(
        latest[
            "Close"
        ]
    )


    prev_close = float(
        previous[
            "Close"
        ]
    )


    change = (
        close
        - prev_close
    )


    change_pct = (
        change
        / prev_close
        * 100
    )


    technical = (
        calculate_technical_score(
            latest
        )
    )


    price_position = (
        calculate_price_position(
            latest
        )
    )


    temperature = (
        calculate_market_temperature(
            latest
        )
    )


    scenarios = (
        calculate_historical_scenarios(
            df
        )
    )


    return {

        "name":
            name,

        "symbol":
            symbol,

        "source":
            source,

        "date":
            df.index[-1]
            .strftime(
                "%Y-%m-%d"
            ),

        "close":
            round(
                close,
                2
            ),

        "previous_close":
            round(
                prev_close,
                2
            ),

        "change":
            round(
                change,
                2
            ),

        "change_pct":
            round(
                change_pct,
                2
            ),

        "ma5":
            round_or_none(
                latest["MA5"]
            ),

        "ma20":
            round_or_none(
                latest["MA20"]
            ),

        "ma60":
            round_or_none(
                latest["MA60"]
            ),

        "ma200":
            round_or_none(
                latest["MA200"]
            ),

        "boll_upper":
            round_or_none(
                latest["BOLL_UPPER"]
            ),

        "boll_mid":
            round_or_none(
                latest["BOLL_MID"]
            ),

        "boll_lower":
            round_or_none(
                latest["BOLL_LOWER"]
            ),

        "rsi14":
            round_or_none(
                latest["RSI14"]
            ),

        "macd_dif":
            round_or_none(
                latest["DIF"]
            ),

        "macd_dea":
            round_or_none(
                latest["DEA"]
            ),

        "macd_hist":
            round_or_none(
                latest["MACD"]
            ),

        "high20":
            round_or_none(
                latest["HIGH20"]
            ),

        "low20":
            round_or_none(
                latest["LOW20"]
            ),

        "high52w":
            round_or_none(
                latest["HIGH252"]
            ),

        "low52w":
            round_or_none(
                latest["LOW252"]
            ),

        "drawdown_52w_pct":
            round_or_none(
                latest[
                    "DRAWDOWN_52W"
                ]
            ),

        "dev_ma200_pct":
            round_or_none(
                latest[
                    "DEV_MA200"
                ]
            ),

        "return20_pct":
            round_or_none(
                latest["RET20"]
            ),

        "return60_pct":
            round_or_none(
                latest["RET60"]
            ),

        "volatility20":
            round_or_none(
                latest["VOL20"]
            ),

        "volatility_percentile_3y":
            calculate_volatility_percentile_3y(
                df
            ),

        "price_position":
            price_position,

        "market_temperature":
            temperature["score"],

        "temperature_state":
            temperature["state"],

        "price_temperature":
            temperature,

        "technical_score":
            technical["score"],

        "technical_state":
            technical["state"],

        "technical_reasons":
            technical["reasons"],

        "market_score":
            technical["score"],

        "market_state":
            technical["state"],

        "market_reasons":
            technical["reasons"],

        "scenario_probability":
            scenarios,

        "history":
            build_history(
                df
            ),
    }


# =========================================================
# 行情数据源
# =========================================================

def get_yahoo_history(
    name,
    symbol
):

    print(
        (
            "正在获取长期历史："
            f"{name} ({symbol})"
        )
    )


    df = (
        yf.Ticker(
            symbol
        )
        .history(
            period="10y",
            interval="1d",
            auto_adjust=False
        )
    )


    if df.empty:

        raise ValueError(
            f"{name} Yahoo未返回历史行情"
        )


    df = df[
        [
            "Open",
            "High",
            "Low",
            "Close"
        ]
    ].dropna()


    if len(df) < 320:

        raise ValueError(
            f"{name} Yahoo长期历史数据不足"
        )


    return build_result(
        name,
        symbol,
        "Yahoo",
        df
    )


def get_sse50_tencent():

    name = "上证50"

    code = "sh000016"

    url = (
        "https://web.ifzq.gtimg.cn/"
        "appstock/app/fqkline/get"
    )


    params = {

        "param":
            f"{code},day,,,1500,qfq"

    }


    print(
        f"正在通过腾讯获取长期历史：{name}"
    )


    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=25
    )


    response.raise_for_status()


    result = (
        response.json()
    )


    stock_data = (
        result
        .get(
            "data",
            {}
        )
        .get(
            code,
            {}
        )
    )


    klines = (
        stock_data.get(
            "qfqday"
        )
        or stock_data.get(
            "day"
        )
        or []
    )


    if len(klines) < 320:

        raise ValueError(
            (
                "腾讯上证50长期K线不足320日，"
                f"实际 {len(klines)} 日"
            )
        )


    records = []


    for item in klines:

        try:

            records.append(
                {
                    "Date":
                        item[0],

                    "Open":
                        float(
                            item[1]
                        ),

                    "Close":
                        float(
                            item[2]
                        ),

                    "High":
                        float(
                            item[3]
                        ),

                    "Low":
                        float(
                            item[4]
                        ),
                }
            )

        except Exception:
            continue


    df = pd.DataFrame(
        records
    )


    df["Date"] = (
        pd.to_datetime(
            df["Date"]
        )
    )


    df = (
        df
        .set_index(
            "Date"
        )
        .sort_index()
    )


    return build_result(
        "上证50",
        "000016.SH",
        "Tencent",
        df
    )


def get_sse50_data():

    try:

        return (
            get_sse50_tencent()
        )

    except Exception as e:

        print(
            f"腾讯长期数据获取失败：{e}"
        )


        data = (
            get_yahoo_history(
                "上证50",
                "000016.SS"
            )
        )


        data[
            "symbol"
        ] = "000016.SH"


        return data


# =========================================================
# 将估值/情绪挂载到指数，
# 并保留旧前端兼容字段
# =========================================================

def attach_model_layers(
    index_key,
    data,
    valuation,
    macro
):

    if data.get(
        "error"
    ):

        return data


    data[
        "valuation"
    ] = valuation


    data[
        "valuation_note"
    ] = (
        "核心长期决策以估值为主；"
        "价格位置、情绪、技术和短期历史情境均为辅助观察。"
    )


    if index_key == "sse50":

        data[
            "sentiment"
        ] = (
            calculate_sse50_risk_state(
                data
            )
        )

    else:

        data[
            "sentiment"
        ] = (
            calculate_us_sentiment(
                index_key,
                macro
            )
        )


    # 兼容 Strategy 3.1 前端。
    # 下一步前端将正式改为
    # valuation / price_position。

    compat_score = valuation.get(
        "attractiveness_score_compat"
    )


    if compat_score is None:

        compat_score = 50


    data[
        "allocation_score"
    ] = compat_score


    data[
        "allocation_state"
    ] = valuation.get(
        "state",
        "数据不足"
    )


    data[
        "allocation_action_label"
    ] = valuation.get(
        "action",
        "估值数据不足"
    )


    data[
        "allocation_reasons"
    ] = valuation.get(
        "reasons",
        []
    )


    data[
        "strategy_basis"
    ] = {

        "core":
            "valuation",

        "investment_amount":
            "valuation_driven_periodic_variable_amount",

        "price_position":
            "observation_only",

        "sentiment":
            "observation_only",

        "technical":
            "observation_only",

        "scenario_probability":
            "observation_only",

        "holding_profit":
            "record_only_not_decision_input",
    }


    return data


# =========================================================
# 使用说明
# =========================================================

def build_guide():

    return {

        "valuation": {

            "title":
                "估值状态",

            "question":
                (
                    "当前指数相对于自身价值和历史估值，"
                    "处于什么区域？"
                ),

            "meaning":
                (
                    "估值是长期买入、持有、暂停新增或再平衡的核心依据。"
                    "不同指数采用不同估值方法。"
                ),
        },


        "allocation": {

            "title":
                "核心行动",

            "question":
                (
                    "当前应该定投、持有还是再平衡？"
                ),

            "meaning":
                (
                    "低估时定投，合理区间以持有为主，"
                    "明显高估时才考虑分批再平衡。"
                ),
        },


        "price_temperature": {

            "title":
                "长期价格位置",

            "question":
                (
                    "当前价格相对MA200和52周高点处于哪里？"
                ),

            "meaning":
                (
                    "只描述价格位置，不替代估值，"
                    "也不直接决定买卖。"
                ),
        },


        "sentiment": {

            "title":
                "市场风险情绪",

            "question":
                (
                    "市场当前更谨慎还是更亢奋？"
                ),

            "meaning":
                (
                    "VIX/VXN或波动状态仅用于解释市场环境，"
                    "不直接触发长期买卖。"
                ),
        },


        "technical": {

            "title":
                "技术状态",

            "question":
                (
                    "当前短期趋势处于什么状态？"
                ),

            "meaning":
                (
                    "MA、RSI、MACD只用于描述短期走势，"
                    "不改变估值决定的定投纪律。"
                ),
        },


        "probability": {

            "title":
                "短期历史情境",

            "question":
                (
                    "历史上相似状态之后20个交易日"
                    "更常见什么走势？"
                ),

            "meaning":
                (
                    "这是历史条件频率，"
                    "不参与估值、定投金额或卖出判断。"
                ),
        },
    }


# =========================================================
# 主程序
# =========================================================

def main():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    history_store = (
        load_valuation_history()
    )


    macro = (
        get_macro_context()
    )


    market_data = {

        "updated_at":
            now_shanghai(),

        "strategy_version":
            "4.0-valuation-first",

        "theory": {

            "core":
                (
                    "估值决定长期行动，"
                    "定期不定额决定低估区内投入强度"
                ),

            "auxiliary":
                (
                    "价格位置、情绪、技术与20日情境仅作观察"
                ),

            "sell_rule":
                (
                    "不以持仓盈亏作为卖出理由；"
                    "明显高估、基本面恶化或出现显著更优替代品时"
                    "才考虑再平衡"
                ),
        },

        "guide":
            build_guide(),

        "macro":
            macro,

        "indices":
            {},
    }


    # =====================================================
    # 1) 行情
    # =====================================================

    try:

        market_data[
            "indices"
        ][
            "sse50"
        ] = (
            get_sse50_data()
        )

    except Exception as e:

        market_data[
            "indices"
        ][
            "sse50"
        ] = {

            "name":
                "上证50",

            "symbol":
                "000016.SH",

            "error":
                str(e)
        }


    for key, item in (
        US_INDICES.items()
    ):

        try:

            market_data[
                "indices"
            ][
                key
            ] = (
                get_yahoo_history(
                    item[
                        "name"
                    ],
                    item[
                        "symbol"
                    ]
                )
            )

        except Exception as e:

            market_data[
                "indices"
            ][
                key
            ] = {

                "name":
                    item[
                        "name"
                    ],

                "symbol":
                    item[
                        "symbol"
                    ],

                "error":
                    str(e)
            }


    # =====================================================
    # 2) 估值
    # =====================================================

    valuations = {}


    try:

        if not market_data[
            "indices"
        ][
            "sse50"
        ].get(
            "error"
        ):

            valuations[
                "sse50"
            ] = (
                build_sse50_valuation(
                    market_data[
                        "indices"
                    ][
                        "sse50"
                    ],
                    history_store,
                    macro
                )
            )

    except Exception as e:

        valuations[
            "sse50"
        ] = {

            "state":
                "数据不足",

            "action":
                "估值数据不足，暂不判断",

            "error":
                str(e),

            "reasons":
                [],

            "attractiveness_score_compat":
                None,
        }


    try:

        valuations[
            "sp500"
        ] = (
            build_sp500_valuation(
                history_store,
                macro
            )
        )

    except Exception as e:

        valuations[
            "sp500"
        ] = {

            "state":
                "数据不足",

            "action":
                "估值数据不足，暂不判断",

            "error":
                str(e),

            "reasons":
                [],

            "attractiveness_score_compat":
                None,
        }


    try:

        valuations[
            "nasdaq100"
        ] = (
            build_ndx_valuation(
                history_store,
                macro
            )
        )

    except Exception as e:

        valuations[
            "nasdaq100"
        ] = {

            "state":
                "数据不足",

            "action":
                "估值数据不足，暂不判断",

            "error":
                str(e),

            "reasons":
                [],

            "attractiveness_score_compat":
                None,
        }


    # =====================================================
    # 3) 合并层级
    # =====================================================

    for key, data in list(
        market_data[
            "indices"
        ].items()
    ):

        if data.get(
            "error"
        ):

            continue


        valuation = (
            valuations.get(
                key
            )
            or {
                "state":
                    "数据不足",

                "action":
                    "估值数据不足，暂不判断",

                "reasons":
                    [],

                "attractiveness_score_compat":
                    None,
            }
        )


        market_data[
            "indices"
        ][
            key
        ] = (
            attach_model_layers(
                key,
                data,
                valuation,
                macro
            )
        )


    # =====================================================
    # 保存估值历史
    # =====================================================

    save_valuation_history(
        history_store
    )


    # =====================================================
    # 保存 market.json
    # =====================================================

    with open(
        MARKET_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            market_data,
            f,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )


    # =====================================================
    # 日志
    # =====================================================

    print(
        "\n======================================"
    )

    print(
        "INDEX RADAR Strategy 4.0 更新完成"
    )

    print(
        "核心：估值优先；其他层仅辅助观察"
    )

    print(
        "======================================"
    )


    for key, data in (
        market_data[
            "indices"
        ].items()
    ):

        print(
            f"\n{key}"
        )


        if data.get(
            "error"
        ):

            print(
                "ERROR:",
                data[
                    "error"
                ]
            )

            continue


        val = data.get(
            "valuation",
            {}
        )


        print(
            "valuation:",
            val.get(
                "state"
            ),
            "|",
            val.get(
                "action"
            )
        )


        print(
            "PE:",
            val.get(
                "pe"
            ),
            "| percentile:",
            val.get(
                "pe_percentile_10y"
            )
        )


        print(
            "price position:",
            data.get(
                "price_position",
                {}
            ).get(
                "state"
            )
        )


        print(
            "sentiment:",
            data.get(
                "sentiment",
                {}
            ).get(
                "state"
            )
        )


        print(
            "technical:",
            data.get(
                "technical_state"
            )
        )


if __name__ == "__main__":

    main()
