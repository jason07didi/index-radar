import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import yfinance as yf


# =========================================================
# 基础配置
# =========================================================

US_INDICES = {
    "nasdaq100": {
        "name": "纳斯达克100",
        "symbol": "^NDX"
    },
    "sp500": {
        "name": "标普500",
        "symbol": "^GSPC"
    }
}


# =========================================================
# 技术指标
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    close = df["Close"]

    # -------------------------
    # 均线
    # -------------------------

    df["MA5"] = close.rolling(5).mean()
    df["MA20"] = close.rolling(20).mean()
    df["MA60"] = close.rolling(60).mean()


    # -------------------------
    # BOLL
    # 20日均线 ± 2倍标准差
    # -------------------------

    boll_mid = close.rolling(20).mean()
    boll_std = close.rolling(20).std(ddof=0)

    df["BOLL_MID"] = boll_mid
    df["BOLL_UPPER"] = boll_mid + 2 * boll_std
    df["BOLL_LOWER"] = boll_mid - 2 * boll_std


    # -------------------------
    # RSI14
    # Wilder方法
    # -------------------------

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

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

    rs = avg_gain / avg_loss

    df["RSI14"] = 100 - (100 / (1 + rs))


    # -------------------------
    # MACD
    # DIF = EMA12 - EMA26
    # DEA = DIF的EMA9
    # MACD柱 = 2 × (DIF - DEA)
    # -------------------------

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    df["DIF"] = ema12 - ema26

    df["DEA"] = df["DIF"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["MACD"] = 2 * (
        df["DIF"] - df["DEA"]
    )

    return df


# =========================================================
# 统一整理结果
# =========================================================

def build_result(name, symbol, source, df):

    df = calculate_indicators(df)

    if len(df) < 60:
        raise ValueError(
            f"{name} 有效交易数据不足60日"
        )

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    close = float(latest["Close"])
    prev_close = float(previous["Close"])

    change = close - prev_close
    change_pct = change / prev_close * 100


    # -------------------------
    # 最近20日高低点
    # 后面用来判断压力与支撑
    # -------------------------

    recent20 = df.tail(20)

    high20 = float(recent20["High"].max())
    low20 = float(recent20["Low"].min())


    # -------------------------
    # 最近60个交易日走势图
    # -------------------------

    history = []

    for index, row in df.tail(60).iterrows():

        history.append({
            "date": index.strftime("%Y-%m-%d"),

            "open": round(
                float(row["Open"]),
                2
            ),

            "high": round(
                float(row["High"]),
                2
            ),

            "low": round(
                float(row["Low"]),
                2
            ),

            "close": round(
                float(row["Close"]),
                2
            ),

            "ma5": (
                round(float(row["MA5"]), 2)
                if pd.notna(row["MA5"])
                else None
            ),

            "ma20": (
                round(float(row["MA20"]), 2)
                if pd.notna(row["MA20"])
                else None
            ),

            "ma60": (
                round(float(row["MA60"]), 2)
                if pd.notna(row["MA60"])
                else None
            ),

            "boll_upper": (
                round(float(row["BOLL_UPPER"]), 2)
                if pd.notna(row["BOLL_UPPER"])
                else None
            ),

            "boll_mid": (
                round(float(row["BOLL_MID"]), 2)
                if pd.notna(row["BOLL_MID"])
                else None
            ),

            "boll_lower": (
                round(float(row["BOLL_LOWER"]), 2)
                if pd.notna(row["BOLL_LOWER"])
                else None
            )
        })


    return {

        "name": name,
        "symbol": symbol,
        "source": source,

        "date": df.index[-1].strftime(
            "%Y-%m-%d"
        ),

        "close": round(close, 2),

        "previous_close": round(
            prev_close,
            2
        ),

        "change": round(
            change,
            2
        ),

        "change_pct": round(
            change_pct,
            2
        ),


        # =====================
        # 均线
        # =====================

        "ma5": round(
            float(latest["MA5"]),
            2
        ),

        "ma20": round(
            float(latest["MA20"]),
            2
        ),

        "ma60": round(
            float(latest["MA60"]),
            2
        ),


        # =====================
        # BOLL
        # =====================

        "boll_upper": round(
            float(latest["BOLL_UPPER"]),
            2
        ),

        "boll_mid": round(
            float(latest["BOLL_MID"]),
            2
        ),

        "boll_lower": round(
            float(latest["BOLL_LOWER"]),
            2
        ),


        # =====================
        # RSI
        # =====================

        "rsi14": round(
            float(latest["RSI14"]),
            2
        ),


        # =====================
        # MACD
        # =====================

        "macd_dif": round(
            float(latest["DIF"]),
            2
        ),

        "macd_dea": round(
            float(latest["DEA"]),
            2
        ),

        "macd_hist": round(
            float(latest["MACD"]),
            2
        ),


        # =====================
        # 20日区间
        # =====================

        "high20": round(
            high20,
            2
        ),

        "low20": round(
            low20,
            2
        ),


        # =====================
        # 60日历史
        # =====================

        "history": history
    }


# =========================================================
# Yahoo Finance
# =========================================================

def get_yahoo_history(name, symbol):

    print(
        f"正在获取：{name} ({symbol})"
    )

    ticker = yf.Ticker(symbol)

    df = ticker.history(
        period="1y",
        interval="1d",
        auto_adjust=False
    )

    df = df[
        [
            "Open",
            "High",
            "Low",
            "Close"
        ]
    ]

    df = df.dropna(
        subset=["Close"]
    )

    if len(df) < 60:

        raise ValueError(
            f"{name} Yahoo历史数据不足"
        )

    return build_result(
        name,
        symbol,
        "Yahoo",
        df
    )


# =========================================================
# 腾讯财经：上证50
# =========================================================

def get_sse50_tencent():

    name = "上证50"
    code = "sh000016"

    print(
        f"正在通过腾讯获取：{name}"
    )

    url = (
        "https://web.ifzq.gtimg.cn/"
        "appstock/app/fqkline/get"
    )

    params = {
        "param": f"{code},day,,,180,qfq"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/124.0.0.0 "
            "Safari/537.36"
        )
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    result = response.json()

    if "data" not in result:

        raise ValueError(
            "腾讯接口没有返回data"
        )

    if code not in result["data"]:

        raise ValueError(
            "腾讯接口没有返回上证50"
        )

    stock_data = result["data"][code]

    klines = (
        stock_data.get("qfqday")
        or stock_data.get("day")
        or []
    )

    if len(klines) < 60:

        raise ValueError(
            "腾讯上证50历史数据不足"
        )


    records = []

    for item in klines:

        try:

            records.append({
                "Date": item[0],
                "Open": float(item[1]),
                "Close": float(item[2]),
                "High": float(item[3]),
                "Low": float(item[4])
            })

        except Exception:

            continue


    df = pd.DataFrame(records)

    if len(df) < 60:

        raise ValueError(
            "上证50有效K线不足60日"
        )

    df["Date"] = pd.to_datetime(
        df["Date"]
    )

    df = df.set_index("Date")

    df = df.sort_index()


    return build_result(
        "上证50",
        "000016.SH",
        "Tencent",
        df
    )


# =========================================================
# 上证50备用源
# =========================================================

def get_sse50_data():

    try:

        return get_sse50_tencent()

    except Exception as e:

        print(
            f"腾讯获取失败：{e}"
        )

        print(
            "尝试Yahoo备用源..."
        )

        data = get_yahoo_history(
            "上证50",
            "000016.SS"
        )

        data["symbol"] = "000016.SH"

        return data


# =========================================================
# 主程序
# =========================================================

def main():

    market_data = {

        "updated_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "indices": {}
    }


    # =========================
    # 上证50
    # =========================

    try:

        market_data["indices"][
            "sse50"
        ] = get_sse50_data()

    except Exception as e:

        print(
            f"上证50最终获取失败：{e}"
        )

        market_data["indices"][
            "sse50"
        ] = {

            "name": "上证50",

            "symbol": "000016.SH",

            "error": str(e)
        }


    # =========================
    # 美股
    # =========================

    for key, item in US_INDICES.items():

        try:

            market_data["indices"][
                key
            ] = get_yahoo_history(
                item["name"],
                item["symbol"]
            )

        except Exception as e:

            print(
                f"{item['name']} 获取失败：{e}"
            )

            market_data["indices"][
                key
            ] = {

                "name": item["name"],

                "symbol": item["symbol"],

                "error": str(e)
            }


    # =========================
    # 保存
    # =========================

    output_path = Path(
        "data/market.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            market_data,
            f,
            ensure_ascii=False,
            indent=2
        )


    print(
        "\n行情及技术指标已经更新"
    )

    print(
        json.dumps(
            market_data,
            ensure_ascii=False,
            indent=2
        )[:5000]
    )


if __name__ == "__main__":

    main()
