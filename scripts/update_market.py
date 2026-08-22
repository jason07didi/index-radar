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
# 技术指标计算
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    close = df["Close"]


    # =====================================================
    # MA5 / MA20 / MA60
    # =====================================================

    df["MA5"] = close.rolling(5).mean()

    df["MA20"] = close.rolling(20).mean()

    df["MA60"] = close.rolling(60).mean()


    # =====================================================
    # BOLL
    #
    # 中轨 = MA20
    # 上轨 = MA20 + 2 × 20日标准差
    # 下轨 = MA20 - 2 × 20日标准差
    # =====================================================

    boll_mid = close.rolling(20).mean()

    boll_std = close.rolling(20).std(ddof=0)

    df["BOLL_MID"] = boll_mid

    df["BOLL_UPPER"] = boll_mid + 2 * boll_std

    df["BOLL_LOWER"] = boll_mid - 2 * boll_std


    # =====================================================
    # RSI14
    #
    # Wilder方法
    # =====================================================

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


    df["RSI14"] = 100 - (
        100 / (1 + rs)
    )


    # =====================================================
    # MACD
    #
    # DIF = EMA12 - EMA26
    # DEA = DIF的EMA9
    # MACD柱 = 2 × (DIF - DEA)
    # =====================================================

    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()


    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()


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
# 市场趋势评分
#
# 目的：
# 将市场技术状态转换成0~100分
#
# 注意：
# 这里只判断“市场本身”
# 不考虑用户仓位和盈利率
#
# 用户仓位策略后面在网页端完成
# =========================================================

def calculate_market_score(latest):

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


    boll_upper = float(
        latest["BOLL_UPPER"]
    )

    boll_mid = float(
        latest["BOLL_MID"]
    )

    boll_lower = float(
        latest["BOLL_LOWER"]
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


    # =====================================================
    # 初始分
    # =====================================================

    score = 50

    reasons = []


    # =====================================================
    # 1. 价格与MA20
    # ±8分
    # =====================================================

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


    # =====================================================
    # 2. 价格与MA60
    # ±10分
    # =====================================================

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


    # =====================================================
    # 3. MA5与MA20
    # ±5分
    # =====================================================

    if ma5 > ma20:

        score += 5

        reasons.append(
            "MA5位于MA20上方"
        )

    else:

        score -= 5

        reasons.append(
            "MA5位于MA20下方"
        )


    # =====================================================
    # 4. MA20与MA60
    # ±7分
    # =====================================================

    if ma20 > ma60:

        score += 7

        reasons.append(
            "MA20位于MA60上方"
        )

    else:

        score -= 7

        reasons.append(
            "MA20位于MA60下方"
        )


    # =====================================================
    # 5. MACD DIF与DEA
    # ±6分
    # =====================================================

    if dif > dea:

        score += 6

        reasons.append(
            "MACD保持多头结构"
        )

    else:

        score -= 6

        reasons.append(
            "MACD处于空头结构"
        )


    # =====================================================
    # 6. MACD柱
    # ±4分
    # =====================================================

    if macd > 0:

        score += 4

    else:

        score -= 4


    # =====================================================
    # 7. RSI
    # =====================================================

    if 50 <= rsi <= 70:

        score += 6

        reasons.append(
            "RSI处于偏强区间"
        )


    elif 40 <= rsi < 50:

        score -= 2

        reasons.append(
            "RSI动能偏弱"
        )


    elif 30 <= rsi < 40:

        score -= 5

        reasons.append(
            "RSI处于弱势区间"
        )


    elif rsi < 30:

        score -= 8

        reasons.append(
            "RSI进入超卖区"
        )


    elif 70 < rsi <= 75:

        score += 2

        reasons.append(
            "RSI处于强势区域"
        )


    elif rsi > 75:

        score -= 4

        reasons.append(
            "RSI进入较高位置"
        )


    # =====================================================
    # 8. BOLL中轨
    # ±5分
    # =====================================================

    if close > boll_mid:

        score += 5

        reasons.append(
            "指数运行于BOLL中轨上方"
        )

    else:

        score -= 5

        reasons.append(
            "指数运行于BOLL中轨下方"
        )


    # =====================================================
    # 9. BOLL极端位置
    # =====================================================

    if close <= boll_lower:

        score -= 5

        reasons.append(
            "指数接近或跌破BOLL下轨"
        )


    elif close >= boll_upper:

        score -= 3

        reasons.append(
            "指数接近或突破BOLL上轨"
        )


    # =====================================================
    # 限制到0~100
    # =====================================================

    score = max(
        0,
        min(100, score)
    )


    # =====================================================
    # 市场状态
    # =====================================================

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

        "score": score,

        "state": state,

        "reasons": reasons
    }


# =========================================================
# 将原始K线整理成JSON结果
# =========================================================

def build_result(
    name,
    symbol,
    source,
    df
):

    # =====================================================
    # 计算指标
    # =====================================================

    df = calculate_indicators(
        df
    )


    # =====================================================
    # 至少需要60个交易日
    # =====================================================

    if len(df) < 60:

        raise ValueError(
            f"{name} 有效交易数据不足60日"
        )


    # =====================================================
    # 最新 / 前一交易日
    # =====================================================

    latest = df.iloc[-1]

    previous = df.iloc[-2]


    # =====================================================
    # 市场评分
    # =====================================================

    strategy = calculate_market_score(
        latest
    )


    # =====================================================
    # 最新价格
    # =====================================================

    close = float(
        latest["Close"]
    )

    prev_close = float(
        previous["Close"]
    )


    change = (
        close - prev_close
    )


    change_pct = (
        change
        / prev_close
        * 100
    )


    # =====================================================
    # 最近20日最高 / 最低
    # =====================================================

    recent20 = df.tail(20)


    high20 = float(
        recent20["High"].max()
    )


    low20 = float(
        recent20["Low"].min()
    )


    # =====================================================
    # 最近60日历史数据
    #
    # 用于网页绘制：
    #
    # 收盘
    # MA5
    # MA20
    # MA60
    # BOLL
    # =====================================================

    history = []


    for index, row in df.tail(60).iterrows():

        history.append({

            "date": index.strftime(
                "%Y-%m-%d"
            ),


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
                round(
                    float(row["MA5"]),
                    2
                )
                if pd.notna(
                    row["MA5"]
                )
                else None
            ),


            "ma20": (
                round(
                    float(row["MA20"]),
                    2
                )
                if pd.notna(
                    row["MA20"]
                )
                else None
            ),


            "ma60": (
                round(
                    float(row["MA60"]),
                    2
                )
                if pd.notna(
                    row["MA60"]
                )
                else None
            ),


            "boll_upper": (
                round(
                    float(
                        row["BOLL_UPPER"]
                    ),
                    2
                )
                if pd.notna(
                    row["BOLL_UPPER"]
                )
                else None
            ),


            "boll_mid": (
                round(
                    float(
                        row["BOLL_MID"]
                    ),
                    2
                )
                if pd.notna(
                    row["BOLL_MID"]
                )
                else None
            ),


            "boll_lower": (
                round(
                    float(
                        row["BOLL_LOWER"]
                    ),
                    2
                )
                if pd.notna(
                    row["BOLL_LOWER"]
                )
                else None
            )
        })


    # =====================================================
    # 最终结果
    # =====================================================

    return {

        "name": name,

        "symbol": symbol,

        "source": source,


        # =================================================
        # 日期
        # =================================================

        "date": df.index[-1].strftime(
            "%Y-%m-%d"
        ),


        # =================================================
        # 行情
        # =================================================

        "close": round(
            close,
            2
        ),


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


        # =================================================
        # MA
        # =================================================

        "ma5": round(
            float(
                latest["MA5"]
            ),
            2
        ),


        "ma20": round(
            float(
                latest["MA20"]
            ),
            2
        ),


        "ma60": round(
            float(
                latest["MA60"]
            ),
            2
        ),


        # =================================================
        # BOLL
        # =================================================

        "boll_upper": round(
            float(
                latest["BOLL_UPPER"]
            ),
            2
        ),


        "boll_mid": round(
            float(
                latest["BOLL_MID"]
            ),
            2
        ),


        "boll_lower": round(
            float(
                latest["BOLL_LOWER"]
            ),
            2
        ),


        # =================================================
        # RSI
        # =================================================

        "rsi14": round(
            float(
                latest["RSI14"]
            ),
            2
        ),


        # =================================================
        # MACD
        # =================================================

        "macd_dif": round(
            float(
                latest["DIF"]
            ),
            2
        ),


        "macd_dea": round(
            float(
                latest["DEA"]
            ),
            2
        ),


        "macd_hist": round(
            float(
                latest["MACD"]
            ),
            2
        ),


        # =================================================
        # 20日最高 / 最低
        # =================================================

        "high20": round(
            high20,
            2
        ),


        "low20": round(
            low20,
            2
        ),


        # =================================================
        # 市场评分
        # =================================================

        "market_score": strategy[
            "score"
        ],


        "market_state": strategy[
            "state"
        ],


        "market_reasons": strategy[
            "reasons"
        ],


        # =================================================
        # 60日走势图
        # =================================================

        "history": history
    }


# =========================================================
# Yahoo Finance
#
# 用于：
# 纳斯达克100
# 标普500
#
# 上证50备用
# =========================================================

def get_yahoo_history(
    name,
    symbol
):

    print(
        f"正在获取：{name} ({symbol})"
    )


    ticker = yf.Ticker(
        symbol
    )


    # =====================================================
    # 获取一年日线
    # =====================================================

    df = ticker.history(

        period="1y",

        interval="1d",

        auto_adjust=False
    )


    # =====================================================
    # 只保留OHLC
    # =====================================================

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
# 腾讯财经
#
# 用于：
# 上证50
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


    # =====================================================
    # 请求180个交易日
    # =====================================================

    params = {

        "param": (
            f"{code},day,,,180,qfq"
        )
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


    # =====================================================
    # 检查返回结果
    # =====================================================

    if "data" not in result:

        raise ValueError(
            "腾讯接口没有返回data"
        )


    if code not in result["data"]:

        raise ValueError(
            "腾讯接口没有返回上证50"
        )


    stock_data = result[
        "data"
    ][
        code
    ]


    # =====================================================
    # 指数通常使用day
    #
    # 部分证券可能返回qfqday
    # =====================================================

    klines = (

        stock_data.get(
            "qfqday"
        )

        or

        stock_data.get(
            "day"
        )

        or []
    )


    if len(klines) < 60:

        raise ValueError(
            "腾讯上证50历史数据不足"
        )


    # =====================================================
    # 腾讯K线格式
    #
    # 日期
    # 开盘
    # 收盘
    # 最高
    # 最低
    # ...
    # =====================================================

    records = []


    for item in klines:

        try:

            records.append({

                "Date": item[0],

                "Open": float(
                    item[1]
                ),

                "Close": float(
                    item[2]
                ),

                "High": float(
                    item[3]
                ),

                "Low": float(
                    item[4]
                )
            })

        except Exception:

            continue


    # =====================================================
    # 转换DataFrame
    # =====================================================

    df = pd.DataFrame(
        records
    )


    if len(df) < 60:

        raise ValueError(
            "上证50有效K线不足60日"
        )


    df["Date"] = pd.to_datetime(
        df["Date"]
    )


    df = df.set_index(
        "Date"
    )


    df = df.sort_index()


    return build_result(

        "上证50",

        "000016.SH",

        "Tencent",

        df
    )


# =========================================================
# 上证50
#
# 腾讯优先
# Yahoo备用
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


        # =================================================
        # 对外统一使用000016.SH
        # =================================================

        data["symbol"] = (
            "000016.SH"
        )


        return data


# =========================================================
# 主程序
# =========================================================

def main():

    market_data = {

        "updated_at": datetime.now(
            ZoneInfo(
                "Asia/Shanghai"
            )
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "indices": {}
    }


    # =====================================================
    # 上证50
    # =====================================================

    try:

        market_data[
            "indices"
        ][
            "sse50"
        ] = get_sse50_data()


    except Exception as e:

        print(
            f"上证50最终获取失败：{e}"
        )


        market_data[
            "indices"
        ][
            "sse50"
        ] = {

            "name": "上证50",

            "symbol": "000016.SH",

            "error": str(e)
        }


    # =====================================================
    # 纳斯达克100 / 标普500
    # =====================================================

    for key, item in US_INDICES.items():

        try:

            market_data[
                "indices"
            ][
                key
            ] = get_yahoo_history(

                item["name"],

                item["symbol"]
            )


        except Exception as e:

            print(
                f"{item['name']} 获取失败：{e}"
            )


            market_data[
                "indices"
            ][
                key
            ] = {

                "name": item[
                    "name"
                ],

                "symbol": item[
                    "symbol"
                ],

                "error": str(e)
            }


    # =====================================================
    # 保存market.json
    # =====================================================

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
        "\n======================================"
    )

    print(
        "行情、技术指标和市场评分已经更新"
    )

    print(
        "======================================"
    )


    # =====================================================
    # 控制日志长度
    # =====================================================

    print(
        json.dumps(
            market_data,
            ensure_ascii=False,
            indent=2
        )[:6000]
    )


# =========================================================
# 程序入口
# =========================================================

if __name__ == "__main__":

    main()
