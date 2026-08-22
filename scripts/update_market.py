import json
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import yfinance as yf


# =========================================================
# INDEX RADAR Strategy 3.0
#
# 核心逻辑：
#
# 1. 长期配置吸引力
#    越低估/越深回撤 → 越值得长期关注
#
# 2. 市场温度
#    越高 → 越不适合追涨
#    越低 → 越值得关注分批配置
#
# 3. 短期技术状态
#    MA / RSI / MACD / BOLL
#    用于决定加仓节奏，而不是长期价值
#
# 4. 历史相似情境概率
#    寻找历史上与当前状态相似的日期，
#    统计未来20个交易日的表现
#
# 5. 宏观情绪
#    VIX
#    美国10年期国债收益率
#
# 注意：
# 当前长期配置吸引力仍属于“价格型代理指标”。
# PE / PB / 盈利收益率等真正估值数据后续再接入。
# =========================================================


# =========================================================
# 美股指数
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

    df = df.copy().sort_index()

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


    # 年线
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
    # Wilder方法
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
        -
        (
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
        *
        (
            df["DIF"]
            - df["DEA"]
        )

    )


    # =====================================================
    # 20 / 60 日收益率
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
    #
    # 252个交易日
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
    # 距离52周高点的回撤
    #
    # 例如：
    #
    # -5  → 距离高点回撤5%
    # -20 → 距离高点回撤20%
    # =====================================================

    df["DRAWDOWN_52W"] = (

        (
            close
            / df["HIGH252"]
        )

        - 1

    ) * 100


    # =====================================================
    # 价格相对于均线的偏离
    # =====================================================

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
    #
    # 不同指数点位差异很大，
    # 用价格标准化后用于历史相似度匹配
    # =====================================================

    df["MACD_NORM"] = (

        df["MACD"]
        / close
        * 100

    )


    return df


# =========================================================
# 短期技术评分
#
# 技术强 ≠ 长期值得追涨
#
# 它以后主要用来判断：
#
# 是否企稳
# 是否开始修复
# 加仓是否需要等待确认
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


    # =====================================================
    # MA20
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
    # MA60
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
    # MA5 / MA20
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
    # MA20 / MA60
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
    # MACD
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


    if macd > 0:

        score += 4


    else:

        score -= 4


    # =====================================================
    # RSI
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
    # BOLL
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

            max(

                0,

                min(
                    100,
                    score
                )

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
# 长期配置吸引力
#
# 这里与趋势策略相反：
#
# 涨得越高
# → 不代表越值得加仓
#
# 回撤越深
# 长期价格越合理
# → 配置吸引力提高
#
# 当前尚未包含PE/PB等基本面估值。
# =========================================================

def calculate_allocation_attractiveness(latest):

    drawdown = float(
        latest["DRAWDOWN_52W"]
    )


    dev200 = float(
        latest["DEV_MA200"]
    )


    rsi = float(
        latest["RSI14"]
    )


    ret20 = float(
        latest["RET20"]
    )


    score = 50

    reasons = []


    # =====================================================
    # 1. 52周回撤
    # =====================================================

    if drawdown >= -3:

        score -= 12

        reasons.append(
            "价格接近52周高位，安全边际偏低"
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
    # 2. MA200偏离
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
    # 3. RSI
    #
    # 只赋较低权重
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
    # 4. 20日涨跌
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

            max(

                0,

                min(
                    100,
                    score
                )

            )

        )

    )


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

        "reasons":
            reasons

    }


# =========================================================
# 市场温度
#
# 0   = 极冷
# 50  = 中性
# 100 = 极热
#
# 对长期投资者：
#
# 热度越高
# → 越不应该追涨
#
# 热度越低
# → 越值得关注长期分批配置
# =========================================================

def calculate_market_temperature(latest):

    dev200 = float(
        latest["DEV_MA200"]
    )


    drawdown = float(
        latest["DRAWDOWN_52W"]
    )


    rsi = float(
        latest["RSI14"]
    )


    ret20 = float(
        latest["RET20"]
    )


    temperature = 50


    # =====================================================
    # MA200
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
    # 回撤
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

            max(

                0,

                min(
                    100,
                    temperature
                )

            )

        )

    )


    if temperature >= 80:

        state = "过热"


    elif temperature >= 65:

        state = "偏热"


    elif temperature >= 40:

        state = "中性"


    elif temperature >= 25:

        state = "偏冷"


    else:

        state = "深冷"


    return {

        "score":
            temperature,

        "state":
            state

    }


# =========================================================
# 根据三种方向概率
# 给出用户容易理解的路径名称
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

        if (
            up_pct
            >= down_pct + 8
        ):

            return "震荡偏强"


        if (
            down_pct
            >= up_pct + 8
        ):

            return "震荡偏弱"


        return "震荡整理"


    if up_pct > down_pct:

        return "震荡偏强"


    if down_pct > up_pct:

        return "震荡偏弱"


    return "震荡整理"


# =========================================================
# 历史相似情境概率
#
# 当前定义：
#
# 未来20个交易日收益：
#
# > +3%  → 上涨
# -3~+3% → 震荡
# < -3%  → 下跌
#
# 这是历史条件频率，
# 不是确定性预测。
# =========================================================

def calculate_historical_scenarios(
    df,
    horizon=20,
    max_samples=120,
    direction_threshold=3.0
):

    current = (
        df.iloc[-1]
    )


    # =====================================================
    # 用于寻找历史相似状态的指标
    # =====================================================

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
            current[feature]
        ):

            return None


    current_features = {

        feature:
            float(
                current[feature]
            )

        for feature
        in required_features

    }


    # =====================================================
    # 相似度标准化尺度
    # =====================================================

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


    # =====================================================
    # 从拥有完整MA200之后开始
    # =====================================================

    start_index = 252


    # =====================================================
    # 必须留下未来20日
    # =====================================================

    end_index = (

        len(df)

        - horizon

        - 1

    )


    if end_index <= start_index:

        return None


    # =====================================================
    # 每隔3个交易日选择一个候选点
    #
    # 防止连续日期高度重复
    # =====================================================

    for i in range(

        start_index,

        end_index,

        3

    ):

        row = (
            df.iloc[i]
        )


        valid = True

        distance_parts = []


        for feature in required_features:

            value = row[
                feature
            ]


            if pd.isna(value):

                valid = False

                break


            difference = (

                (
                    float(value)

                    - current_features[
                        feature
                    ]
                )

                / scales[
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


    if len(candidates) < 30:

        return None


    # =====================================================
    # 距离越小
    # 越相似
    # =====================================================

    candidates = sorted(

        candidates,

        key=lambda x:
            x["distance"]

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


    # =====================================================
    # 分析历史相似日期之后20日
    # =====================================================

    for candidate in selected:

        i = candidate[
            "index"
        ]


        distance = candidate[
            "distance"
        ]


        # =================================================
        # 相似度越高
        # 权重越高
        # =================================================

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


        if len(future) < horizon:

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


        # =================================================
        # 三种方向
        # =================================================

        if (
            future_return
            > direction_threshold
        ):

            up_weight += (
                weight
            )


        elif (
            future_return
            < -direction_threshold
        ):

            down_weight += (
                weight
            )


        else:

            sideways_weight += (
                weight
            )


        # =================================================
        # 当前历史状态对应的关键参考位
        # =================================================

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


        # =================================================
        # 未来20日是否曾站上当前MA20
        # =================================================

        if (

            future[
                "Close"
            ]

            > current_ma20

        ).any():

            above_ma20_weight += (
                weight
            )


        # =================================================
        # 未来20日是否曾站上当前MA60
        # =================================================

        if (

            future[
                "Close"
            ]

            > current_ma60

        ).any():

            above_ma60_weight += (
                weight
            )


        # =================================================
        # 未来最低 / 最高
        # =================================================

        future_low = float(

            future[
                "Low"
            ]
            .min()

        )


        future_high = float(

            future[
                "High"
            ]
            .max()

        )


        if (
            future_low
            < current_low20
        ):

            break_low20_weight += (
                weight
            )


        if (
            future_high
            > current_high20
        ):

            break_high20_weight += (
                weight
            )


    if total_weight <= 0:

        return None


    # =====================================================
    # 权重转换为百分比
    # =====================================================

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


    # =====================================================
    # 保证三者加起来严格等于100%
    # =====================================================

    sideways_pct = (

        100

        - up_pct

        - down_pct

    )


    sideways_pct = max(

        0,

        sideways_pct

    )


    # =====================================================
    # 历史平均收益
    # =====================================================

    weighted_avg_return = (

        weighted_return_sum

        / total_weight

    )


    # =====================================================
    # 历史中位数收益
    # =====================================================

    median_return = float(

        pd.Series(
            future_returns
        )
        .median()

    )


    # =====================================================
    # 平均相似距离
    # =====================================================

    average_distance = (

        sum(
            selected_distances
        )

        /
        len(
            selected_distances
        )

    )


    # =====================================================
    # 有效样本量
    #
    # 比简单显示120个更合理。
    # 因为某些样本权重非常低。
    # =====================================================

    effective_sample_size = (

        (
            total_weight ** 2
        )

        /
        sum_weight_squared

        if sum_weight_squared > 0

        else 0

    )


    # =====================================================
    # 可信度
    # =====================================================

    if (

        effective_sample_size >= 60

        and average_distance <= 1.25

    ):

        confidence = "较高"


    elif (

        effective_sample_size >= 35

        and average_distance <= 1.75

    ):

        confidence = "中等"


    else:

        confidence = "较低"


    # =====================================================
    # 最可能路径
    # =====================================================

    path_label = (
        build_path_label(

            up_pct,

            sideways_pct,

            down_pct

        )
    )


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
            path_label,

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
#
# 252个交易日
#
# 前端以后可以切换：
#
# 3个月
# 6个月
# 1年
#
# 不需要后台重新获取数据。
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
                round(
                    float(
                        row["Open"]
                    ),
                    2
                ),


            "high":
                round(
                    float(
                        row["High"]
                    ),
                    2
                ),


            "low":
                round(
                    float(
                        row["Low"]
                    ),
                    2
                ),


            "close":
                round(
                    float(
                        row["Close"]
                    ),
                    2
                ),


            # =================================================
            # MA5仍保留给后台/后续功能
            # 但下一版图表默认不展示
            # =================================================

            "ma5":
                (

                    round(
                        float(
                            row["MA5"]
                        ),
                        2
                    )

                    if pd.notna(
                        row["MA5"]
                    )

                    else None

                ),


            "ma20":
                (

                    round(
                        float(
                            row["MA20"]
                        ),
                        2
                    )

                    if pd.notna(
                        row["MA20"]
                    )

                    else None

                ),


            "ma60":
                (

                    round(
                        float(
                            row["MA60"]
                        ),
                        2
                    )

                    if pd.notna(
                        row["MA60"]
                    )

                    else None

                ),


            # =================================================
            # MA200 年线
            # =================================================

            "ma200":
                (

                    round(
                        float(
                            row["MA200"]
                        ),
                        2
                    )

                    if pd.notna(
                        row["MA200"]
                    )

                    else None

                ),


            "boll_upper":
                (

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


            "boll_mid":
                (

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


            "boll_lower":
                (

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


    return history


# =========================================================
# 整理单个指数
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


    # =====================================================
    # MA200 + 历史概率
    # 至少需要320日
    # =====================================================

    if len(df) < 320:

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
            latest[field]
        ):

            raise ValueError(

                f"{name} 无法计算长期指标 {field}"

            )


    # =====================================================
    # 三套判断
    # =====================================================

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


    # =====================================================
    # 未来20日历史条件概率
    # =====================================================

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

        - prev_close

    )


    change_pct = (

        change

        / prev_close

        * 100

    )


    # =====================================================
    # 最近252个交易日
    # =====================================================

    history = (

        build_history(

            df,

            periods=252

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
            round(
                float(
                    latest["MA5"]
                ),
                2
            ),

        "ma20":
            round(
                float(
                    latest["MA20"]
                ),
                2
            ),

        "ma60":
            round(
                float(
                    latest["MA60"]
                ),
                2
            ),

        "ma200":
            round(
                float(
                    latest["MA200"]
                ),
                2
            ),


        # =================================================
        # BOLL
        # =================================================

        "boll_upper":
            round(
                float(
                    latest[
                        "BOLL_UPPER"
                    ]
                ),
                2
            ),

        "boll_mid":
            round(
                float(
                    latest[
                        "BOLL_MID"
                    ]
                ),
                2
            ),

        "boll_lower":
            round(
                float(
                    latest[
                        "BOLL_LOWER"
                    ]
                ),
                2
            ),


        # =================================================
        # RSI / MACD
        # =================================================

        "rsi14":
            round(
                float(
                    latest[
                        "RSI14"
                    ]
                ),
                2
            ),

        "macd_dif":
            round(
                float(
                    latest[
                        "DIF"
                    ]
                ),
                2
            ),

        "macd_dea":
            round(
                float(
                    latest[
                        "DEA"
                    ]
                ),
                2
            ),

        "macd_hist":
            round(
                float(
                    latest[
                        "MACD"
                    ]
                ),
                2
            ),


        # =================================================
        # 20日位置
        # =================================================

        "high20":
            round(
                float(
                    latest[
                        "HIGH20"
                    ]
                ),
                2
            ),

        "low20":
            round(
                float(
                    latest[
                        "LOW20"
                    ]
                ),
                2
            ),


        # =================================================
        # 52周位置
        # =================================================

        "high52w":
            round(
                float(
                    latest[
                        "HIGH252"
                    ]
                ),
                2
            ),

        "low52w":
            round(
                float(
                    latest[
                        "LOW252"
                    ]
                ),
                2
            ),


        # =================================================
        # 长期价格状态
        # =================================================

        "drawdown_52w_pct":
            round(
                float(
                    latest[
                        "DRAWDOWN_52W"
                    ]
                ),
                2
            ),

        "dev_ma200_pct":
            round(
                float(
                    latest[
                        "DEV_MA200"
                    ]
                ),
                2
            ),

        "return20_pct":
            round(
                float(
                    latest[
                        "RET20"
                    ]
                ),
                2
            ),

        "return60_pct":
            round(
                float(
                    latest[
                        "RET60"
                    ]
                ),
                2
            ),

        "volatility20":
            round(
                float(
                    latest[
                        "VOL20"
                    ]
                ),
                2
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

        "allocation_reasons":
            attractiveness[
                "reasons"
            ],


        # =================================================
        # 市场温度
        # =================================================

        "market_temperature":
            temperature[
                "score"
            ],

        "temperature_state":
            temperature[
                "state"
            ],


        # =================================================
        # 短期技术
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
        # 兼容旧网页
        #
        # 下一步重构前端后，
        # 这些字段可以不再作为核心展示
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
        # 未来20日概率
        # =================================================

        "scenario_probability":
            scenarios,


        # =================================================
        # 估值说明
        # =================================================

        "valuation_note":
            (
                "当前长期配置吸引力为价格型代理评分，"
                "尚未接入PE、PB、盈利收益率等基本面估值数据。"
            ),


        # =================================================
        # 最近1年走势图
        # =================================================

        "history":
            history

    }


# =========================================================
# Yahoo Finance
#
# 纳指100 / 标普500
#
# 获取10年历史
# =========================================================

def get_yahoo_history(
    name,
    symbol
):

    print(

        f"正在获取长期历史：{name} ({symbol})"

    )


    ticker = yf.Ticker(
        symbol
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

    ]


    df = df.dropna(

        subset=[

            "Open",

            "High",

            "Low",

            "Close"

        ]

    )


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


# =========================================================
# 腾讯财经
#
# 上证50
#
# 获取约1500个交易日
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


    if len(df) < 320:

        raise ValueError(

            "上证50有效长期K线不足320日"

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


# =========================================================
# 上证50
#
# 腾讯优先
# Yahoo备用
# =========================================================

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


        data["symbol"] = (

            "000016.SH"

        )


        return data


# =========================================================
# VIX
#
# 用于美国市场情绪
# =========================================================

def get_vix_context():

    ticker = yf.Ticker(
        "^VIX"
    )


    df = ticker.history(

        period="5y",

        interval="1d",

        auto_adjust=False

    )


    if df.empty:

        raise ValueError(

            "VIX未返回数据"

        )


    close = (

        df["Close"]
        .dropna()

    )


    if len(close) < 30:

        raise ValueError(

            "VIX历史数据不足"

        )


    current = float(

        close.iloc[-1]

    )


    previous = float(

        close.iloc[-2]

    )


    # =====================================================
    # 当前VIX在过去5年的历史百分位
    # =====================================================

    percentile_5y = (

        (
            close
            <= current
        )
        .mean()

        * 100

    )


    # =====================================================
    # 情绪标签
    # =====================================================

    if current < 15:

        state = "低波动"

        sentiment = (
            "市场情绪较平静"
        )


    elif current < 20:

        state = "正常"

        sentiment = (
            "市场情绪总体正常"
        )


    elif current < 30:

        state = "偏高"

        sentiment = (
            "市场担忧上升"
        )


    elif current < 40:

        state = "恐慌"

        sentiment = (
            "市场处于明显恐慌区"
        )


    else:

        state = "极端恐慌"

        sentiment = (
            "市场波动进入极端区间"
        )


    return {

        "name":
            "VIX",

        "symbol":
            "^VIX",

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
            state,

        "sentiment":
            sentiment

    }


# =========================================================
# 美国10年期国债收益率
#
# ^TNX 数值例如：
#
# 4.7
#
# 即约4.7%
# =========================================================

def get_us10y_context():

    ticker = yf.Ticker(
        "^TNX"
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

        df["Close"]
        .dropna()

    )


    if len(close) < 22:

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


    # =====================================================
    # 20日变化
    #
    # 1个百分点 = 100bp
    # =====================================================

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
# 宏观数据
#
# 即使VIX或美债获取失败，
# 也不能让三个指数更新失败。
# =========================================================

def get_macro_context():

    macro = {

        "updated_at":

            datetime.now(

                ZoneInfo(
                    "Asia/Shanghai"
                )

            )
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    }


    # =====================================================
    # VIX
    # =====================================================

    try:

        macro["vix"] = (

            get_vix_context()

        )


    except Exception as e:

        macro["vix"] = {

            "name":
                "VIX",

            "symbol":
                "^VIX",

            "error":
                str(e)

        }


    # =====================================================
    # US10Y
    # =====================================================

    try:

        macro["us10y"] = (

            get_us10y_context()

        )


    except Exception as e:

        macro["us10y"] = {

            "name":
                "美国10年期国债收益率",

            "symbol":
                "^TNX",

            "error":
                str(e)

        }


    return macro


# =========================================================
# 主程序
# =========================================================

def main():

    market_data = {

        "updated_at":

            datetime.now(

                ZoneInfo(
                    "Asia/Shanghai"
                )

            )
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            ),


        "strategy_version":

            "3.0-value-allocation-probability",


        # =================================================
        # 宏观市场情绪
        # =================================================

        "macro":

            get_macro_context(),


        "indices":

            {}

    }


    # =====================================================
    # 上证50
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
    # 保存 market.json
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


    # =====================================================
    # 日志
    # =====================================================

    print(

        "\n======================================"

    )


    print(

        "INDEX RADAR Strategy 3.0 更新完成"

    )


    print(

        "1年趋势 + MA200 + 历史概率 + VIX + US10Y"

    )


    print(

        "======================================"

    )


    # =====================================================
    # 宏观摘要
    # =====================================================

    macro = market_data.get(

        "macro",

        {}

    )


    print(

        "\n宏观情绪："

    )


    print(

        json.dumps(

            macro,

            ensure_ascii=False,

            indent=2

        )

    )


    # =====================================================
    # 指数摘要
    # =====================================================

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

            "close:",

            data[
                "close"
            ]

        )


        print(

            "allocation:",

            data[
                "allocation_score"
            ],

            data[
                "allocation_state"
            ]

        )


        print(

            "temperature:",

            data[
                "market_temperature"
            ],

            data[
                "temperature_state"
            ]

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


        print(

            "MA200:",

            data[
                "ma200"
            ]

        )


        print(

            "drawdown52w:",

            data[
                "drawdown_52w_pct"
            ]

        )


        print(

            "dev_ma200:",

            data[
                "dev_ma200_pct"
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


# =========================================================
# 程序入口
# =========================================================

if __name__ == "__main__":

    main()
