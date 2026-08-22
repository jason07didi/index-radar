import json
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf


# =========================================================
# INDEX RADAR Strategy 3.1
#
# 目标：
# 1) 长期配置吸引力：回答“长期资金现在值不值得增加”
# 2) 价格温度：回答“价格相对长期锚点热不热”
# 3) 指数专属市场情绪：
#    - 上证50：指数自身回撤 / 动量 / 波动率
#    - 纳斯达克100：VXN + 美债 + 指数自身状态
#    - 标普500：VIX + 美债 + 指数自身状态
# 4) 短期技术：回答“什么时候分批动手”
# 5) 历史相似情境：回答“未来20日历史上更常见哪条路径”
#
# 注意：
# 当前仍未接入 PE / PB / 盈利收益率等严格意义上的估值数据。
# =========================================================


US_INDICES = {
    "nasdaq100": {
        "name": "纳斯达克100",
        "symbol": "^NDX"
    },

    "sp500": {
        "name": "标普500",
        "symbol": "^GSPC"
    },
}


# =========================================================
# 通用工具
# =========================================================

def clamp(value, low=0, high=100):

    return max(
        low,
        min(
            high,
            value
        )
    )


def round_or_none(
    value,
    digits=2
):

    if (
        value is None
        or pd.isna(value)
    ):
        return None

    return round(
        float(value),
        digits
    )


def now_shanghai():

    return datetime.now(
        ZoneInfo(
            "Asia/Shanghai"
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =========================================================
# 技术指标
# =========================================================

def calculate_indicators(df):

    df = (
        df.copy()
        .sort_index()
    )

    close = df["Close"]
    high = df["High"]
    low = df["Low"]


    # =====================================================
    # 均线
    # =====================================================

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


    # =====================================================
    # BOLL
    # =====================================================

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

    df["BOLL_MID"] = (
        boll_mid
    )

    df["BOLL_UPPER"] = (
        boll_mid
        + 2 * boll_std
    )

    df["BOLL_LOWER"] = (
        boll_mid
        - 2 * boll_std
    )


    # =====================================================
    # RSI14
    # Wilder
    # =====================================================

    delta = (
        close
        .diff()
    )

    gain = (
        delta
        .clip(lower=0)
    )

    loss = (
        -delta
        .clip(upper=0)
    )

    avg_gain = (
        gain
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    avg_loss = (
        loss
        .ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        )
        .mean()
    )

    rs = (
        avg_gain
        / avg_loss
    )

    df["RSI14"] = (
        100
        - (
            100
            / (1 + rs)
        )
    )


    # =====================================================
    # MACD
    # =====================================================

    ema12 = (
        close
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        close
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

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


    # =====================================================
    # 收益率
    # =====================================================

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


    # =====================================================
    # 20日年化波动率
    # =====================================================

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


    # =====================================================
    # 20日区间
    # =====================================================

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


    # =====================================================
    # 52周区间
    # =====================================================

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


    # =====================================================
    # 长期价格位置
    # =====================================================

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


    # =====================================================
    # MACD标准化
    # 用于不同指数之间的历史状态匹配
    # =====================================================

    df["MACD_NORM"] = (
        df["MACD"]
        / close
        * 100
    )

    return df


# =========================================================
# 短期技术评分
# =========================================================

def calculate_technical_score(latest):

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

    boll_mid = float(
        latest["BOLL_MID"]
    )

    boll_upper = float(
        latest["BOLL_UPPER"]
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

        reasons.append(
            "MA5位于MA20上方"
        )

    else:

        score -= 5

        reasons.append(
            "MA5位于MA20下方"
        )


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


    if macd > 0:

        score += 4

    else:

        score -= 4


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


    score = int(
        round(
            clamp(score)
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
# 长期配置吸引力
# =========================================================

def allocation_action_label(score):

    if score >= 80:

        return "值得重点关注"

    if score >= 65:

        return "适合适度增强"

    if score >= 45:

        return "正常定投"

    if score >= 30:

        return "谨慎增加"

    return "暂停额外加仓"


def calculate_allocation_attractiveness(latest):

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

    rsi = float(
        latest[
            "RSI14"
        ]
    )

    ret20 = float(
        latest[
            "RET20"
        ]
    )


    score = 50

    reasons = []


    # =====================================================
    # 52周回撤
    # =====================================================

    if drawdown >= -3:

        score -= 12

        reasons.append(
            "价格接近52周高位，价格安全边际偏低"
        )


    elif drawdown >= -8:

        score -= 6

        reasons.append(
            "价格距离52周高点较近"
        )


    elif drawdown >= -15:

        score += 4

        reasons.append(
            "市场已出现一定幅度回撤"
        )


    elif drawdown >= -25:

        score += 12

        reasons.append(
            "市场处于中等回撤区间"
        )


    elif drawdown >= -35:

        score += 20

        reasons.append(
            "市场处于较深回撤区间"
        )


    else:

        score += 26

        reasons.append(
            "市场处于极深回撤区间"
        )


    # =====================================================
    # MA200偏离
    # =====================================================

    if dev200 > 20:

        score -= 22

        reasons.append(
            "价格显著高于MA200，长期价格偏热"
        )


    elif dev200 > 10:

        score -= 12

        reasons.append(
            "价格明显高于MA200"
        )


    elif dev200 > 3:

        score -= 5

        reasons.append(
            "价格温和高于MA200"
        )


    elif dev200 >= -5:

        score += 2

        reasons.append(
            "价格接近长期均衡区域"
        )


    elif dev200 >= -15:

        score += 10

        reasons.append(
            "价格低于MA200，长期配置吸引力改善"
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


    # =====================================================
    # RSI
    # =====================================================

    if rsi > 75:

        score -= 8

        reasons.append(
            "短期交易热度较高"
        )


    elif rsi > 65:

        score -= 4


    elif rsi < 35:

        score += 6

        reasons.append(
            "短期情绪已明显降温"
        )


    elif rsi < 45:

        score += 3


    # =====================================================
    # 近20日涨跌
    # =====================================================

    if ret20 > 12:

        score -= 7

        reasons.append(
            "近20日上涨较快，不宜追涨"
        )


    elif ret20 > 6:

        score -= 3


    elif ret20 < -12:

        score += 6

        reasons.append(
            "近20日快速回撤，长期配置价格改善"
        )


    elif ret20 < -6:

        score += 3


    score = int(
        round(
            clamp(score)
        )
    )


    # -----------------------------------------------------
    # 保留旧字段，兼容目前前端
    # -----------------------------------------------------

    if score >= 80:

        state = "高吸引力"

    elif score >= 65:

        state = "较高吸引力"

    elif score >= 45:

        state = "中性"

    elif score >= 30:

        state = "偏低"

    else:

        state = "低吸引力"


    return {

        "score":
            score,

        "state":
            state,

        "action_label":
            allocation_action_label(
                score
            ),

        "reasons":
            reasons

    }


# =========================================================
# 价格温度
#
# 注意：
# 这是“价格位置”，不是“市场情绪”。
#
# 0   = 很冷
# 50  = 平衡
# 100 = 很热
# =========================================================

def temperature_label(score):

    if score < 25:

        return "明显偏冷"

    if score < 40:

        return "偏冷"

    if score <= 60:

        return "平衡"

    if score < 75:

        return "偏热"

    return "明显过热"


def calculate_market_temperature(latest):

    dev200 = float(
        latest[
            "DEV_MA200"
        ]
    )

    drawdown = float(
        latest[
            "DRAWDOWN_52W"
        ]
    )

    rsi = float(
        latest[
            "RSI14"
        ]
    )

    ret20 = float(
        latest[
            "RET20"
        ]
    )


    temperature = 50


    # =====================================================
    # 年线偏离
    # =====================================================

    if dev200 > 20:

        temperature += 20

    elif dev200 > 10:

        temperature += 12

    elif dev200 > 3:

        temperature += 6

    elif dev200 >= -5:

        temperature += 0

    elif dev200 >= -15:

        temperature -= 10

    else:

        temperature -= 18


    # =====================================================
    # 52周回撤
    # =====================================================

    if drawdown >= -3:

        temperature += 15

    elif drawdown >= -8:

        temperature += 8

    elif drawdown >= -15:

        temperature += 0

    elif drawdown >= -25:

        temperature -= 10

    elif drawdown >= -35:

        temperature -= 17

    else:

        temperature -= 22


    # =====================================================
    # RSI
    # =====================================================

    if rsi >= 75:

        temperature += 10

    elif rsi >= 65:

        temperature += 6

    elif rsi >= 55:

        temperature += 3

    elif rsi >= 45:

        temperature += 0

    elif rsi >= 35:

        temperature -= 4

    else:

        temperature -= 8


    # =====================================================
    # 20日涨跌
    # =====================================================

    if ret20 > 12:

        temperature += 8

    elif ret20 > 6:

        temperature += 4

    elif ret20 < -12:

        temperature -= 8

    elif ret20 < -6:

        temperature -= 4


    temperature = int(
        round(
            clamp(
                temperature
            )
        )
    )


    return {

        "score":
            temperature,

        "state":
            temperature_label(
                temperature
            ),

        "meaning":
            (
                "价格温度描述当前价格相对长期锚点是否偏热或偏冷。"
                "对长期定投者而言，温度低通常意味着价格机会在改善，"
                "但不等于短期已经见底。"
            )

    }


# =========================================================
# 历史相似情境
# =========================================================

def build_path_label(
    up_pct,
    sideways_pct,
    down_pct
):

    if (
        up_pct >= 45
        and
        up_pct >= down_pct + 10
    ):

        return "偏强上行"


    if (
        down_pct >= 45
        and
        down_pct >= up_pct + 10
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


    required_features = [

        "DEV_MA20",

        "DEV_MA60",

        "DEV_MA200",

        "RSI14",

        "DRAWDOWN_52W",

        "RET20",

        "MACD_NORM"

    ]


    for feature in required_features:

        if pd.isna(
            current[
                feature
            ]
        ):

            return None


    current_features = {

        feature:
            float(
                current[
                    feature
                ]
            )

        for feature
        in required_features

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
            0.6

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


    # -----------------------------------------------------
    # 每隔3个交易日取一个候选点
    # 减少相邻日期重复
    # -----------------------------------------------------

    for i in range(
        start_index,
        end_index,
        3
    ):

        row = (
            df.iloc[i]
        )

        distance_parts = []

        valid = True


        for feature in required_features:

            value = row[
                feature
            ]


            if pd.isna(
                value
            ):

                valid = False

                break


            difference = (

                (
                    float(value)

                    -
                    current_features[
                        feature
                    ]
                )

                /
                scales[
                    feature
                ]

            )


            distance_parts.append(
                difference ** 2
            )


        if not valid:

            continue


        distance = math.sqrt(

            sum(
                distance_parts
            )

            /
            len(
                distance_parts
            )

        )


        candidates.append({

            "index":
                i,

            "distance":
                distance

        })


    if len(
        candidates
    ) < 30:

        return None


    candidates.sort(

        key=lambda x:
            x[
                "distance"
            ]

    )


    selected = candidates[

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


        if weight <= 0:

            continue


        current_row = (
            df.iloc[i]
        )


        future = df.iloc[

            i + 1
            :
            i + horizon + 1

        ]


        if len(
            future
        ) < horizon:

            continue


        start_close = float(

            current_row[
                "Close"
            ]

        )


        end_close = float(

            future
            .iloc[-1][
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


        future_returns.append(
            future_return
        )


        selected_distances.append(
            distance
        )


        weighted_return_sum += (
            future_return
            * weight
        )


        total_weight += (
            weight
        )


        sum_weight_squared += (
            weight ** 2
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


        current_ma20 = float(

            current_row[
                "MA20"
            ]

        )


        current_ma60 = float(

            current_row[
                "MA60"
            ]

        )


        current_low20 = float(

            current_row[
                "LOW20"
            ]

        )


        current_high20 = float(

            current_row[
                "HIGH20"
            ]

        )


        if (

            future[
                "Close"
            ]

            > current_ma20

        ).any():

            above_ma20_weight += (
                weight
            )


        if (

            future[
                "Close"
            ]

            > current_ma60

        ).any():

            above_ma60_weight += (
                weight
            )


        if float(

            future[
                "Low"
            ]
            .min()

        ) < current_low20:

            break_low20_weight += (
                weight
            )


        if float(

            future[
                "High"
            ]
            .max()

        ) > current_high20:

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


    up_pct = (
        pct(
            up_weight
        )
    )


    down_pct = (
        pct(
            down_weight
        )
    )


    sideways_pct = max(

        0,

        (
            100
            - up_pct
            - down_pct
        )

    )


    weighted_avg_return = (

        weighted_return_sum
        /
        total_weight

    )


    median_return = float(

        pd.Series(
            future_returns
        )
        .median()

    )


    if selected_distances:

        average_distance = (

            sum(
                selected_distances
            )

            /
            len(
                selected_distances
            )

        )

    else:

        average_distance = 999


    if sum_weight_squared > 0:

        effective_sample_size = (

            total_weight ** 2

        ) / sum_weight_squared

    else:

        effective_sample_size = 0


    if (

        effective_sample_size >= 60

        and

        average_distance <= 1.25

    ):

        confidence = "较高"


    elif (

        effective_sample_size >= 35

        and

        average_distance <= 1.75

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
                effective_sample_size,
                1
            ),

        "method":
            "历史相似状态加权频率",

        "confidence":
            confidence,

        "average_distance":
            round(
                average_distance,
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
                weighted_avg_return,
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
                )

        }

    }


# =========================================================
# 最近1年走势图
# =========================================================

def build_history(
    df,
    periods=252
):

    history = []


    for index, row in (

        df
        .tail(periods)
        .iterrows()

    ):

        history.append({

            "date":
                index.strftime(
                    "%Y-%m-%d"
                ),

            "open":
                round_or_none(
                    row[
                        "Open"
                    ]
                ),

            "high":
                round_or_none(
                    row[
                        "High"
                    ]
                ),

            "low":
                round_or_none(
                    row[
                        "Low"
                    ]
                ),

            "close":
                round_or_none(
                    row[
                        "Close"
                    ]
                ),

            "ma5":
                round_or_none(
                    row[
                        "MA5"
                    ]
                ),

            "ma20":
                round_or_none(
                    row[
                        "MA20"
                    ]
                ),

            "ma60":
                round_or_none(
                    row[
                        "MA60"
                    ]
                ),

            "ma200":
                round_or_none(
                    row[
                        "MA200"
                    ]
                ),

            "boll_upper":
                round_or_none(
                    row[
                        "BOLL_UPPER"
                    ]
                ),

            "boll_mid":
                round_or_none(
                    row[
                        "BOLL_MID"
                    ]
                ),

            "boll_lower":
                round_or_none(
                    row[
                        "BOLL_LOWER"
                    ]
                )

        })


    return history


# =========================================================
# 3年波动率历史分位
# =========================================================

def calculate_volatility_percentile_3y(df):

    values = (

        df[
            "VOL20"
        ]
        .dropna()
        .tail(756)

    )


    if len(
        values
    ) < 60:

        return None


    current = float(

        values.iloc[-1]

    )


    percentile = float(

        (
            values
            <= current
        )
        .mean()

        * 100

    )


    return round(

        percentile,

        1

    )


# =========================================================
# 单个指数基础结果
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


    if len(
        df
    ) < 320:

        raise ValueError(

            f"{name} 长期历史数据不足320个交易日"

        )


    latest = (
        df.iloc[-1]
    )

    previous = (
        df.iloc[-2]
    )


    required_latest = [

        "MA200",

        "HIGH252",

        "LOW252",

        "DRAWDOWN_52W",

        "DEV_MA200",

        "RET20",

        "RET60",

        "VOL20"

    ]


    for field in required_latest:

        if pd.isna(
            latest[
                field
            ]
        ):

            raise ValueError(

                f"{name} 无法计算长期指标 {field}"

            )


    technical = (
        calculate_technical_score(
            latest
        )
    )


    attractiveness = (
        calculate_allocation_attractiveness(
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

            df,

            horizon=20,

            max_samples=120,

            direction_threshold=3.0

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
        -
        prev_close

    )


    change_pct = (

        change
        /
        prev_close
        * 100

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


        # =================================================
        # 行情
        # =================================================

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


        # =================================================
        # 均线
        # =================================================

        "ma5":
            round_or_none(
                latest[
                    "MA5"
                ]
            ),

        "ma20":
            round_or_none(
                latest[
                    "MA20"
                ]
            ),

        "ma60":
            round_or_none(
                latest[
                    "MA60"
                ]
            ),

        "ma200":
            round_or_none(
                latest[
                    "MA200"
                ]
            ),


        # =================================================
        # BOLL
        # =================================================

        "boll_upper":
            round_or_none(
                latest[
                    "BOLL_UPPER"
                ]
            ),

        "boll_mid":
            round_or_none(
                latest[
                    "BOLL_MID"
                ]
            ),

        "boll_lower":
            round_or_none(
                latest[
                    "BOLL_LOWER"
                ]
            ),


        # =================================================
        # RSI / MACD
        # =================================================

        "rsi14":
            round_or_none(
                latest[
                    "RSI14"
                ]
            ),

        "macd_dif":
            round_or_none(
                latest[
                    "DIF"
                ]
            ),

        "macd_dea":
            round_or_none(
                latest[
                    "DEA"
                ]
            ),

        "macd_hist":
            round_or_none(
                latest[
                    "MACD"
                ]
            ),


        # =================================================
        # 区间位置
        # =================================================

        "high20":
            round_or_none(
                latest[
                    "HIGH20"
                ]
            ),

        "low20":
            round_or_none(
                latest[
                    "LOW20"
                ]
            ),

        "high52w":
            round_or_none(
                latest[
                    "HIGH252"
                ]
            ),

        "low52w":
            round_or_none(
                latest[
                    "LOW252"
                ]
            ),


        # =================================================
        # 长期状态
        # =================================================

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
                latest[
                    "RET20"
                ]
            ),

        "return60_pct":
            round_or_none(
                latest[
                    "RET60"
                ]
            ),

        "volatility20":
            round_or_none(
                latest[
                    "VOL20"
                ]
            ),

        "volatility_percentile_3y":
            calculate_volatility_percentile_3y(
                df
            ),


        # =================================================
        # 长期配置吸引力
        # =================================================

        "allocation_score":
            attractiveness[
                "score"
            ],

        "allocation_state":
            attractiveness[
                "state"
            ],

        "allocation_action_label":
            attractiveness[
                "action_label"
            ],

        "allocation_reasons":
            attractiveness[
                "reasons"
            ],


        # =================================================
        # 价格温度
        # =================================================

        "market_temperature":
            temperature[
                "score"
            ],

        "temperature_state":
            temperature[
                "state"
            ],

        "price_temperature":
            temperature,


        # =================================================
        # 技术状态
        # =================================================

        "technical_score":
            technical[
                "score"
            ],

        "technical_state":
            technical[
                "state"
            ],

        "technical_reasons":
            technical[
                "reasons"
            ],


        # =================================================
        # 兼容旧前端
        # =================================================

        "market_score":
            technical[
                "score"
            ],

        "market_state":
            technical[
                "state"
            ],

        "market_reasons":
            technical[
                "reasons"
            ],


        # =================================================
        # 历史概率
        # =================================================

        "scenario_probability":
            scenarios,


        # =================================================
        # 估值说明
        # =================================================

        "valuation_note":
            (
                "当前长期配置吸引力仍属于价格型代理评分，"
                "尚未接入PE、PB、盈利收益率等基本面估值数据。"
            ),


        # =================================================
        # 1年历史
        # =================================================

        "history":
            build_history(
                df,
                periods=252
            )

    }


# =========================================================
# Yahoo Finance
# =========================================================

def get_yahoo_history(
    name,
    symbol
):

    print(

        f"正在获取长期历史：{name} ({symbol})"

    )


    ticker = (
        yf.Ticker(
            symbol
        )
    )


    df = ticker.history(

        period="10y",

        interval="1d",

        auto_adjust=False

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


    if len(
        df
    ) < 320:

        raise ValueError(

            f"{name} Yahoo长期历史数据不足"

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

        f"正在通过腾讯获取长期历史：{name}"

    )


    url = (

        "https://web.ifzq.gtimg.cn/"

        "appstock/app/fqkline/get"

    )


    params = {

        "param":
            f"{code},day,,,1500,qfq"

    }


    headers = {

        "User-Agent":
            (
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

        timeout=25

    )


    response.raise_for_status()


    result = (
        response.json()
    )


    if "data" not in result:

        raise ValueError(

            "腾讯接口没有返回data"

        )


    if code not in result[
        "data"
    ]:

        raise ValueError(

            "腾讯接口没有返回上证50"

        )


    stock_data = result[
        "data"
    ][
        code
    ]


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


    if len(
        klines
    ) < 320:

        raise ValueError(

            (
                "腾讯上证50长期K线不足320日，"
                f"实际 {len(klines)} 日"
            )

        )


    records = []


    for item in klines:

        try:

            records.append({

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
                    )

            })


        except Exception:

            continue


    df = pd.DataFrame(
        records
    )


    if len(
        df
    ) < 320:

        raise ValueError(

            "上证50有效长期K线不足320日"

        )


    df["Date"] = (

        pd.to_datetime(
            df[
                "Date"
            ]
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


        print(

            "尝试Yahoo备用源..."

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
# VIX / VXN
# =========================================================

def classify_volatility_index(
    value,
    kind
):

    # =====================================================
    # VXN
    # 纳斯达克100本身波动通常高于标普500
    # 所以阈值与VIX不同
    # =====================================================

    if kind == "vxn":

        if value < 16:

            return "低波动"

        if value < 20:

            return "较低"

        if value < 25:

            return "正常"

        if value < 30:

            return "偏高"

        if value < 40:

            return "高波动"

        return "极端波动"


    # =====================================================
    # VIX
    # =====================================================

    if value < 13:

        return "低波动"

    if value < 16:

        return "较低"

    if value < 20:

        return "正常"

    if value < 25:

        return "偏高"

    if value < 35:

        return "高波动"

    return "极端波动"


def get_volatility_index_context(
    symbol,
    name,
    kind
):

    ticker = (
        yf.Ticker(
            symbol
        )
    )


    df = ticker.history(

        period="5y",

        interval="1d",

        auto_adjust=False

    )


    if df.empty:

        raise ValueError(

            f"{name} 未返回数据"

        )


    close = (

        df[
            "Close"
        ]
        .dropna()

    )


    if len(
        close
    ) < 60:

        raise ValueError(

            f"{name} 历史数据不足"

        )


    current = float(

        close.iloc[-1]

    )


    previous = float(

        close.iloc[-2]

    )


    percentile_5y = float(

        (
            close
            <= current
        )
        .mean()

        * 100

    )


    return {

        "name":
            name,

        "symbol":
            symbol,

        "source":
            "Yahoo Finance / Cboe",

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
                percentile_5y,
                1
            ),

        "state":
            classify_volatility_index(

                current,

                kind

            )

    }


# =========================================================
# 美国10年期国债收益率
# =========================================================

def get_us10y_context():

    ticker = (
        yf.Ticker(
            "^TNX"
        )
    )


    df = ticker.history(

        period="1y",

        interval="1d",

        auto_adjust=False

    )


    if df.empty:

        raise ValueError(

            "美国10年期国债收益率未返回数据"

        )


    close = (

        df[
            "Close"
        ]
        .dropna()

    )


    if len(
        close
    ) < 22:

        raise ValueError(

            "美国10年期国债收益率历史数据不足"

        )


    current = float(

        close.iloc[-1]

    )


    previous = float(

        close.iloc[-2]

    )


    twenty_days_ago = float(

        close.iloc[-21]

    )


    change_20d_bp = (

        current
        - twenty_days_ago

    ) * 100


    if change_20d_bp >= 25:

        trend = "明显上行"


    elif change_20d_bp >= 10:

        trend = "温和上行"


    elif change_20d_bp <= -25:

        trend = "明显下行"


    elif change_20d_bp <= -10:

        trend = "温和下行"


    else:

        trend = "基本稳定"


    return {

        "name":
            "美国10年期国债收益率",

        "symbol":
            "^TNX",

        "source":
            "Yahoo Finance / Cboe",

        "date":
            close.index[-1]
            .strftime(
                "%Y-%m-%d"
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
                change_20d_bp,
                1
            ),

        "trend_20d":
            trend

    }


# =========================================================
# 宏观 / 波动率数据
# =========================================================

def get_macro_context():

    macro = {

        "updated_at":
            now_shanghai()

    }


    # =====================================================
    # VIX
    # =====================================================

    try:

        macro[
            "vix"
        ] = (

            get_volatility_index_context(

                "^VIX",

                "Cboe VIX",

                "vix"

            )

        )


    except Exception as e:

        macro[
            "vix"
        ] = {

            "name":
                "Cboe VIX",

            "symbol":
                "^VIX",

            "error":
                str(e)

        }


    # =====================================================
    # VXN
    # =====================================================

    try:

        macro[
            "vxn"
        ] = (

            get_volatility_index_context(

                "^VXN",

                "Cboe Nasdaq-100 Volatility Index",

                "vxn"

            )

        )


    except Exception as e:

        macro[
            "vxn"
        ] = {

            "name":
                "Cboe Nasdaq-100 Volatility Index",

            "symbol":
                "^VXN",

            "error":
                str(e)

        }


    # =====================================================
    # US10Y
    # =====================================================

    try:

        macro[
            "us10y"
        ] = (

            get_us10y_context()

        )


    except Exception as e:

        macro[
            "us10y"
        ] = {

            "name":
                "美国10年期国债收益率",

            "symbol":
                "^TNX",

            "error":
                str(e)

        }


    return macro


# =========================================================
# 指数专属市场情绪
#
# score：
#
# 0   = 风险偏好非常低
# 50  = 平衡
# 100 = 风险偏好非常高
#
# 注意：
# 市场情绪 ≠ 价格温度
# =========================================================

def sentiment_state(score):

    if score < 25:

        return "明显偏冷"

    if score < 40:

        return "偏冷"

    if score <= 60:

        return "平衡"

    if score < 75:

        return "偏热"

    return "明显过热"


def sentiment_investment_read(score):

    if score < 25:

        return (
            "风险偏好明显下降。对长期定投者而言，"
            "这通常意味着机会可能在改善，但短期仍可能继续波动。"
        )


    if score < 40:

        return (
            "市场情绪偏谨慎。长期资金可以提高关注度，"
            "但仍应结合价格位置与技术企稳分批执行。"
        )


    if score <= 60:

        return (
            "情绪整体平衡，没有明显恐慌或亢奋。"
            "更适合按照长期计划执行，而不是因情绪频繁调整。"
        )


    if score < 75:

        return (
            "风险偏好偏高，追涨意愿增强。"
            "长期投资者应降低额外追价冲动。"
        )


    return (
        "市场情绪明显偏热。即使短期趋势仍强，"
        "也应警惕高位追涨和仓位过度集中。"
    )


# =========================================================
# 通用价格动量情绪组件
# =========================================================

def apply_price_momentum_component(
    score,
    ret20,
    components,
    weight=1.0
):

    if ret20 >= 8:

        score += (
            16
            * weight
        )

        components.append(

            f"近20日上涨 {ret20:.1f}%，风险偏好升温"

        )


    elif ret20 >= 3:

        score += (
            8
            * weight
        )

        components.append(

            f"近20日上涨 {ret20:.1f}%，情绪偏积极"

        )


    elif ret20 <= -8:

        score -= (
            16
            * weight
        )

        components.append(

            (
                f"近20日下跌 {abs(ret20):.1f}%，"
                "市场情绪明显降温"
            )

        )


    elif ret20 <= -3:

        score -= (
            8
            * weight
        )

        components.append(

            (
                f"近20日下跌 {abs(ret20):.1f}%，"
                "市场情绪偏谨慎"
            )

        )


    else:

        components.append(

            "近20日涨跌幅有限，情绪动量接近平衡"

        )


    return score


# =========================================================
# 上证50情绪
#
# 第一版：
# 自身价格 + 回撤 + MA200 + 波动率
#
# 不伪造北向、成交宽度等当前没有的数据。
# =========================================================

def calculate_sse50_sentiment(data):

    score = 50.0

    components = []


    ret20 = float(
        data[
            "return20_pct"
        ]
    )


    drawdown = float(
        data[
            "drawdown_52w_pct"
        ]
    )


    dev200 = float(
        data[
            "dev_ma200_pct"
        ]
    )


    vol_pct = (
        data.get(
            "volatility_percentile_3y"
        )
    )


    rsi = float(
        data[
            "rsi14"
        ]
    )


    score = (

        apply_price_momentum_component(

            score,

            ret20,

            components,

            weight=1.0

        )

    )


    # =====================================================
    # 52周位置
    # =====================================================

    if drawdown >= -3:

        score += 12

        components.append(

            "指数接近52周高位，风险偏好较强"

        )


    elif drawdown >= -8:

        score += 6

        components.append(

            "指数距离52周高位较近"

        )


    elif drawdown <= -25:

        score -= 12

        components.append(

            "指数处于较深回撤，市场情绪明显降温"

        )


    elif drawdown <= -15:

        score -= 7

        components.append(

            "指数处于中等回撤区间"

        )


    # =====================================================
    # MA200
    # =====================================================

    if dev200 >= 10:

        score += 9

        components.append(

            "指数明显高于年线，市场交易情绪偏热"

        )


    elif dev200 >= 3:

        score += 4


    elif dev200 <= -15:

        score -= 9

        components.append(

            "指数明显低于年线，风险偏好较弱"

        )


    elif dev200 <= -5:

        score -= 4


    # =====================================================
    # 波动率历史分位
    # =====================================================

    if vol_pct is not None:

        if (
            vol_pct >= 80
            and
            ret20 < 0
        ):

            score -= 10

            components.append(

                (
                    f"20日波动率处于近3年约 {vol_pct:.0f}% 分位，"
                    "且价格下跌，风险厌恶增强"
                )

            )


        elif (
            vol_pct >= 80
            and
            ret20 >= 0
        ):

            score += 3

            components.append(

                (
                    f"20日波动率处于近3年约 {vol_pct:.0f}% 分位，"
                    "交易活跃度较高"
                )

            )


        elif vol_pct <= 20:

            score += 3

            components.append(

                (
                    f"20日波动率处于近3年约 {vol_pct:.0f}% 分位，"
                    "市场较平静"
                )

            )


    # =====================================================
    # RSI
    # =====================================================

    if rsi >= 70:

        score += 5


    elif rsi <= 35:

        score -= 5


    score = int(

        round(
            clamp(
                score
            )
        )

    )


    return {

        "label":
            "A股蓝筹情绪",

        "score":
            score,

        "state":
            sentiment_state(
                score
            ),

        "confidence":
            "中等",

        "method":
            "上证50自身价格动量 + 回撤 + 年线位置 + 波动率",

        "primary_indicator": {

            "name":
                "上证50自身情绪组合",

            "value":
                score,

            "unit":
                "分"

        },

        "components":
            components,

        "summary":
            sentiment_investment_read(
                score
            ),

        "note":
            (
                "上证50暂未使用VIX类指标。当前情绪评分来自指数自身价格与波动状态，"
                "后续可继续加入成交额、市场宽度等A股专属数据。"
            )

    }


# =========================================================
# 纳斯达克100情绪
#
# 核心：
# VXN
#
# 辅助：
# 纳指自身趋势 + 波动率 + 10Y美债
# =========================================================

def calculate_nasdaq100_sentiment(
    data,
    macro
):

    score = 50.0

    components = []


    ret20 = float(
        data[
            "return20_pct"
        ]
    )


    dev200 = float(
        data[
            "dev_ma200_pct"
        ]
    )


    vol_pct = (
        data.get(
            "volatility_percentile_3y"
        )
    )


    vxn = (
        macro.get(
            "vxn",
            {}
        )
    )


    us10y = (
        macro.get(
            "us10y",
            {}
        )
    )


    vxn_available = (

        bool(vxn)

        and

        not vxn.get(
            "error"
        )

    )


    # =====================================================
    # VXN
    #
    # VXN越高：
    # 市场越恐慌
    #
    # 所以情绪热度分数越低
    # =====================================================

    if vxn_available:

        value = float(
            vxn[
                "value"
            ]
        )


        if value < 16:

            score += 22


        elif value < 20:

            score += 14


        elif value < 25:

            score += 5


        elif value < 30:

            score -= 5


        elif value < 40:

            score -= 16


        else:

            score -= 25


        percentile = float(

            vxn.get(
                "percentile_5y",
                50
            )

        )


        if percentile <= 20:

            score += 7


        elif percentile >= 80:

            score -= 7


        components.append(

            (
                f"VXN {value:.2f}，"
                f"5年历史分位约 {percentile:.0f}%"
            )

        )


    else:

        components.append(

            "VXN暂不可用，本次主要依据纳指自身价格与波动状态"

        )


    # =====================================================
    # 纳指自身动量
    # =====================================================

    score = (

        apply_price_momentum_component(

            score,

            ret20,

            components,

            weight=0.75

        )

    )


    # =====================================================
    # MA200
    # =====================================================

    if dev200 >= 15:

        score += 8

        components.append(

            "纳指明显高于年线，科技股风险偏好偏高"

        )


    elif dev200 >= 5:

        score += 4


    elif dev200 <= -15:

        score -= 8

        components.append(

            "纳指明显低于年线，科技股风险偏好偏弱"

        )


    elif dev200 <= -5:

        score -= 4


    # =====================================================
    # 纳指自身波动率
    # =====================================================

    if (
        vol_pct is not None
        and
        vol_pct >= 80
        and
        ret20 < 0
    ):

        score -= 5

        components.append(

            (
                "纳指自身波动率处于近3年约 "
                f"{vol_pct:.0f}% 分位"
            )

        )


    # =====================================================
    # 10年美债
    #
    # 纳指对利率变化给予较高权重
    # =====================================================

    if (
        us10y
        and
        not us10y.get(
            "error"
        )
    ):

        bp = float(
            us10y[
                "change_20d_bp"
            ]
        )


        if bp >= 25:

            score -= 6

            components.append(

                (
                    f"10年美债近20日上行 {bp:.0f}bp，"
                    "对成长股情绪形成压力"
                )

            )


        elif bp >= 10:

            score -= 3

            components.append(

                (
                    f"10年美债近20日温和上行 "
                    f"{bp:.0f}bp"
                )

            )


        elif bp <= -25:

            score += 6

            components.append(

                (
                    f"10年美债近20日下降 {abs(bp):.0f}bp，"
                    "对成长股情绪较友好"
                )

            )


        elif bp <= -10:

            score += 3


    score = int(

        round(
            clamp(
                score
            )
        )

    )


    primary_indicator = {

        "name":
            "VXN",

        "value":
            (
                vxn.get(
                    "value"
                )

                if vxn_available

                else None
            ),

        "unit":
            "",

        "state":
            (
                vxn.get(
                    "state"
                )

                if vxn_available

                else "暂缺"
            ),

        "percentile_5y":
            (
                vxn.get(
                    "percentile_5y"
                )

                if vxn_available

                else None
            )

    }


    return {

        "label":
            "科技股情绪",

        "score":
            score,

        "state":
            sentiment_state(
                score
            ),

        "confidence":
            (
                "较高"
                if vxn_available
                else "中等"
            ),

        "method":
            "VXN + 纳指自身价格状态 + 10年美债",

        "primary_indicator":
            primary_indicator,

        "components":
            components,

        "summary":
            sentiment_investment_read(
                score
            ),

        "note":
            (
                "纳斯达克100优先使用VXN，因为VXN对应Nasdaq-100期权隐含波动率，"
                "比VIX更贴近科技成长股风险情绪。"
            )

    }


# =========================================================
# 标普500情绪
#
# 核心：
# VIX
#
# 辅助：
# 标普自身趋势 + 波动率 + 10Y美债
# =========================================================

def calculate_sp500_sentiment(
    data,
    macro
):

    score = 50.0

    components = []


    ret20 = float(
        data[
            "return20_pct"
        ]
    )


    dev200 = float(
        data[
            "dev_ma200_pct"
        ]
    )


    vol_pct = (
        data.get(
            "volatility_percentile_3y"
        )
    )


    vix = (

        macro.get(
            "vix",
            {}
        )

    )


    us10y = (

        macro.get(
            "us10y",
            {}
        )

    )


    vix_available = (

        bool(vix)

        and

        not vix.get(
            "error"
        )

    )


    # =====================================================
    # VIX
    # =====================================================

    if vix_available:

        value = float(
            vix[
                "value"
            ]
        )


        if value < 13:

            score += 22


        elif value < 16:

            score += 14


        elif value < 20:

            score += 5


        elif value < 25:

            score -= 5


        elif value < 35:

            score -= 16


        else:

            score -= 25


        percentile = float(

            vix.get(
                "percentile_5y",
                50
            )

        )


        if percentile <= 20:

            score += 7


        elif percentile >= 80:

            score -= 7


        components.append(

            (
                f"VIX {value:.2f}，"
                f"5年历史分位约 {percentile:.0f}%"
            )

        )


    else:

        components.append(

            "VIX暂不可用，本次主要依据标普500自身价格与波动状态"

        )


    # =====================================================
    # 标普自身动量
    # =====================================================

    score = (

        apply_price_momentum_component(

            score,

            ret20,

            components,

            weight=0.70

        )

    )


    # =====================================================
    # MA200
    # =====================================================

    if dev200 >= 15:

        score += 7

        components.append(

            "标普500明显高于年线，风险偏好较高"

        )


    elif dev200 >= 5:

        score += 3


    elif dev200 <= -15:

        score -= 7

        components.append(

            "标普500明显低于年线，风险偏好较弱"

        )


    elif dev200 <= -5:

        score -= 3


    # =====================================================
    # 自身波动率
    # =====================================================

    if (
        vol_pct is not None
        and
        vol_pct >= 80
        and
        ret20 < 0
    ):

        score -= 4

        components.append(

            (
                "标普自身波动率处于近3年约 "
                f"{vol_pct:.0f}% 分位"
            )

        )


    # =====================================================
    # 10年美债
    #
    # 标普权重低于纳指
    # =====================================================

    if (
        us10y
        and
        not us10y.get(
            "error"
        )
    ):

        bp = float(

            us10y[
                "change_20d_bp"
            ]

        )


        if bp >= 25:

            score -= 4

            components.append(

                (
                    f"10年美债近20日上行 {bp:.0f}bp，"
                    "估值折现压力上升"
                )

            )


        elif bp >= 10:

            score -= 2


        elif bp <= -25:

            score += 4

            components.append(

                (
                    f"10年美债近20日下降 {abs(bp):.0f}bp，"
                    "利率环境有所缓和"
                )

            )


        elif bp <= -10:

            score += 2


    score = int(

        round(
            clamp(
                score
            )
        )

    )


    primary_indicator = {

        "name":
            "VIX",

        "value":
            (
                vix.get(
                    "value"
                )

                if vix_available

                else None
            ),

        "unit":
            "",

        "state":
            (
                vix.get(
                    "state"
                )

                if vix_available

                else "暂缺"
            ),

        "percentile_5y":
            (
                vix.get(
                    "percentile_5y"
                )

                if vix_available

                else None
            )

    }


    return {

        "label":
            "美股大盘情绪",

        "score":
            score,

        "state":
            sentiment_state(
                score
            ),

        "confidence":
            (
                "较高"
                if vix_available
                else "中等"
            ),

        "method":
            "VIX + 标普500自身价格状态 + 10年美债",

        "primary_indicator":
            primary_indicator,

        "components":
            components,

        "summary":
            sentiment_investment_read(
                score
            ),

        "note":
            (
                "标普500优先使用VIX，因为VIX基于S&P 500期权，"
                "更贴近美国大盘股整体风险情绪。"
            )

    }


# =========================================================
# 把不同情绪模型挂载到不同指数
# =========================================================

def attach_index_sentiment(
    index_key,
    data,
    macro
):

    if "error" in data:

        return data


    if index_key == "sse50":

        data[
            "sentiment"
        ] = (

            calculate_sse50_sentiment(
                data
            )

        )


    elif index_key == "nasdaq100":

        data[
            "sentiment"
        ] = (

            calculate_nasdaq100_sentiment(

                data,

                macro

            )

        )


    elif index_key == "sp500":

        data[
            "sentiment"
        ] = (

            calculate_sp500_sentiment(

                data,

                macro

            )

        )


    return data


# =========================================================
# 使用说明
#
# 下一步前端会把它做成：
#
# ⓘ 如何使用
#
# 的弹窗
# =========================================================

def build_guide():

    return {

        "allocation": {

            "title":
                "长期配置吸引力",

            "question":
                "现在是否值得增加长期资金？",

            "meaning":
                (
                    "分数越高，代表从回撤、年线位置等价格条件看，"
                    "长期配置吸引力越好。当前尚未加入PE/PB，"
                    "因此不是严格估值。"
                )

        },


        "price_temperature": {

            "title":
                "价格温度",

            "question":
                "当前价格相对长期锚点热不热？",

            "meaning":
                (
                    "温度高代表价格偏热，额外加仓应更克制；"
                    "温度低代表价格机会在改善，"
                    "但不代表短期已经见底。"
                )

        },


        "sentiment": {

            "title":
                "市场情绪",

            "question":
                "投资者现在更恐惧还是更亢奋？",

            "meaning":
                (
                    "不同指数使用不同情绪来源："
                    "上证50使用自身价格与波动状态，"
                    "纳指100优先使用VXN，"
                    "标普500优先使用VIX。"
                )

        },


        "technical": {

            "title":
                "技术状态",

            "question":
                "现在是不是适合分批动手？",

            "meaning":
                (
                    "MA20、MA60、RSI、MACD等只用于辅助加减仓时点，"
                    "不直接代表长期价值。"
                )

        },


        "probability": {

            "title":
                "未来20日历史条件概率",

            "question":
                "历史上类似状态之后更常见哪种路径？",

            "meaning":
                (
                    "上涨、震荡、下跌百分比来自历史相似状态的加权频率，"
                    "不是对未来结果的确定性预测。"
                )

        }

    }


# =========================================================
# 主程序
# =========================================================

def main():

    macro = (
        get_macro_context()
    )


    market_data = {

        "updated_at":
            now_shanghai(),

        "strategy_version":
            "3.1-per-index-sentiment",

        "guide":
            build_guide(),

        "macro":
            macro,

        "indices":
            {}

    }


    # =====================================================
    # 上证50
    # =====================================================

    try:

        data = (
            get_sse50_data()
        )


        market_data[
            "indices"
        ][
            "sse50"
        ] = (

            attach_index_sentiment(

                "sse50",

                data,

                macro

            )

        )


    except Exception as e:

        print(

            f"上证50最终获取失败：{e}"

        )


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


    # =====================================================
    # 纳斯达克100 / 标普500
    # =====================================================

    for key, item in (

        US_INDICES.items()

    ):

        try:

            data = (

                get_yahoo_history(

                    item[
                        "name"
                    ],

                    item[
                        "symbol"
                    ]

                )

            )


            market_data[
                "indices"
            ][
                key
            ] = (

                attach_index_sentiment(

                    key,

                    data,

                    macro

                )

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
    # 保存
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

        "INDEX RADAR Strategy 3.1 更新完成"

    )


    print(

        "指数专属情绪：SSE50 / VXN / VIX"

    )


    print(

        "======================================"

    )


    print(

        "\n宏观数据："

    )


    for key in [

        "vix",

        "vxn",

        "us10y"

    ]:

        item = (

            macro.get(
                key,
                {}
            )

        )


        if item.get(
            "error"
        ):

            print(

                f"{key}: ERROR {item['error']}"

            )


        else:

            print(

                f"{key}:",

                item.get(

                    "value",

                    item.get(
                        "yield_pct"
                    )

                ),

                item.get(

                    "state",

                    item.get(
                        "trend_20d",
                        ""
                    )

                )

            )


    for key, data in (

        market_data[
            "indices"
        ].items()

    ):

        print(

            "\n--------------------------------------"

        )


        print(
            key
        )


        if "error" in data:

            print(

                "ERROR:",

                data[
                    "error"
                ]

            )

            continue


        print(

            "allocation:",

            data[
                "allocation_score"
            ],

            data[
                "allocation_action_label"
            ]

        )


        print(

            "price temperature:",

            data[
                "market_temperature"
            ],

            data[
                "temperature_state"
            ]

        )


        print(

            "sentiment:",

            data[
                "sentiment"
            ][
                "score"
            ],

            data[
                "sentiment"
            ][
                "state"
            ],

            (
                "("
                +
                data[
                    "sentiment"
                ][
                    "label"
                ]
                +
                ")"
            )

        )


        print(

            "technical:",

            data[
                "technical_score"
            ],

            data[
                "technical_state"
            ]

        )


        probability = (

            data.get(
                "scenario_probability"
            )

        )


        if probability:

            print(

                "20日路径:",

                probability[
                    "path_label"
                ]

            )


            print(

                "20日概率:",

                f"上涨 {probability['up_pct']}%",

                f"震荡 {probability['sideways_pct']}%",

                f"下跌 {probability['down_pct']}%"

            )


            print(

                "可信度:",

                probability[
                    "confidence"
                ]

            )


if __name__ == "__main__":

    main()
