import json
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pandas as pd
import yfinance as yf


# =========================================================
# INDEX RADAR
#
# 核心框架：
#
# 1. 长期配置吸引力
#    回撤越深、相对MA200越低 → 配置吸引力通常越高
#
# 2. 市场温度
#    衡量当前价格是否偏热 / 偏冷
#
# 3. 短期技术状态
#    MA / RSI / MACD / BOLL
#    只用于择时辅助，不直接决定长期配置价值
#
# 4. 历史相似情境
#    根据历史相似技术状态，
#    统计未来20个交易日的历史结果
#
# 注意：
# 当前“长期配置吸引力”是价格型代理指标，
# 尚未包含PE / PB / 盈利收益率等基本面估值指标。
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

    df = df.copy()

    df = df.sort_index()

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
    # 20日波动率
    #
    # 年化，仅作为状态描述
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
    # 约252个交易日
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
    # -5  = 比52周高点低5%
    # -20 = 比52周高点低20%
    # =====================================================

    df["DRAWDOWN_52W"] = (

        (
            close
            / df["HIGH252"]
        )

        - 1

    ) * 100


    # =====================================================
    # 与均线偏离
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
    # 不同指数点位不同，
    # 所以需要除以价格才能用于相似度比较
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
# 保留原来的技术体系，
# 但今后它只用于“择时”
# 不再直接决定长期目标仓位。
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

        "score": score,

        "state": state,

        "reasons": reasons

    }


# =========================================================
# 长期配置吸引力
#
# 这是这一版最重要的变化。
#
# 分数越高：
# 当前价格状态越有利于长期配置。
#
# 分数越低：
# 当前价格状态越偏热，
# 不宜因为上涨而机械增加长期仓位。
#
# 注意：
# 该评分暂时属于“价格型代理指标”，
# 不是PE/PB意义上的估值。
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
    #
    # 回撤越深：
    # 长期配置吸引力越高
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
    #
    # 长期价格明显高于MA200：
    # 配置吸引力下降
    #
    # 长期价格低于MA200：
    # 配置吸引力提高
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
    # 权重明显低于长期指标
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
    # 4. 20日涨跌幅
    #
    # 短期急涨降低追高吸引力
    # 短期急跌提高分批配置价值
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

        "score": score,

        "state": state,

        "reasons": reasons

    }


# =========================================================
# 市场温度
#
# 0   = 极冷
# 50  = 中性
# 100 = 极热
#
# 与配置吸引力不同：
#
# 温度越高：
# 越需要警惕追高
#
# 温度越低：
# 越值得关注长期加仓机会
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
    # MA200偏离
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

        "score": temperature,

        "state": state

    }


# =========================================================
# 历史相似情境概率
#
# 目标：
# 找到历史上与当前技术状态相似的日期，
# 然后统计这些日期之后20个交易日发生了什么。
#
# 这不是机器学习预测模型，
# 而是历史相似状态加权频率。
# =========================================================

def calculate_historical_scenarios(
    df,
    horizon=20,
    max_samples=120
):

    # =====================================================
    # 当前状态
    # =====================================================

    current = df.iloc[-1]


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
    # 各指标相似度尺度
    #
    # 数值越小：
    # 对该指标越敏感
    # =====================================================

    scales = {

        "DEV_MA20": 6.0,

        "DEV_MA60": 10.0,

        "DEV_MA200": 15.0,

        "RSI14": 15.0,

        "DRAWDOWN_52W": 12.0,

        "RET20": 10.0,

        "MACD_NORM": 0.6

    }


    candidates = []


    # =====================================================
    # 至少需要200日长期均线
    #
    # 并且历史日期后面必须还剩20日，
    # 防止未来数据不完整。
    # =====================================================

    start_index = 252

    end_index = (
        len(df)
        - horizon
        - 1
    )


    if end_index <= start_index:

        return None


    # =====================================================
    # 每隔3个交易日选取一个历史候选点
    #
    # 这样可以减少大量连续日期重复的问题。
    # =====================================================

    for i in range(
        start_index,
        end_index,
        3
    ):

        row = df.iloc[i]


        valid = True

        distance_parts = []


        for feature in required_features:

            value = row[feature]


            if pd.isna(value):

                valid = False

                break


            difference = (

                (
                    float(value)
                    - current_features[feature]
                )

                / scales[feature]

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

            / len(
                distance_parts
            )

        )


        candidates.append({

            "index": i,

            "distance": distance

        })


    if len(candidates) < 30:

        return None


    # =====================================================
    # 距离越小越相似
    # =====================================================

    candidates = sorted(

        candidates,

        key=lambda x:
            x["distance"]

    )


    selected = candidates[
        :min(
            max_samples,
            len(candidates)
        )
    ]


    total_weight = 0.0


    up_weight = 0.0

    sideways_weight = 0.0

    down_weight = 0.0


    above_ma20_weight = 0.0

    above_ma60_weight = 0.0

    break_low20_weight = 0.0

    break_high20_weight = 0.0


    future_returns = []

    weighted_return_sum = 0.0


    # =====================================================
    # 对历史相似日期进行未来20日统计
    # =====================================================

    for candidate in selected:

        i = candidate["index"]

        distance = candidate["distance"]


        # =================================================
        # 相似度越高权重越大
        # =================================================

        weight = math.exp(
            -0.55 * distance
        )


        if weight <= 0:

            continue


        current_row = df.iloc[i]


        future = df.iloc[
            i + 1:
            i + horizon + 1
        ]


        if len(future) < horizon:

            continue


        start_close = float(
            current_row["Close"]
        )


        end_close = float(
            future.iloc[-1]["Close"]
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


        weighted_return_sum += (
            future_return
            * weight
        )


        total_weight += weight


        # =================================================
        # 三种方向
        #
        # 上涨：
        # 未来20日收益 > +5%
        #
        # 震荡：
        # -5% ~ +5%
        #
        # 下跌：
        # < -5%
        # =================================================

        if future_return > 5:

            up_weight += weight


        elif future_return < -5:

            down_weight += weight


        else:

            sideways_weight += weight


        # =================================================
        # 关键事件
        #
        # 任一未来交易日收盘站上：
        # MA20
        # MA60
        # =================================================

        above_ma20 = (

            future["Close"]
            > future["MA20"]

        ).any()


        above_ma60 = (

            future["Close"]
            > future["MA60"]

        ).any()


        if above_ma20:

            above_ma20_weight += (
                weight
            )


        if above_ma60:

            above_ma60_weight += (
                weight
            )


        # =================================================
        # 当前历史状态下的20日高低点
        # =================================================

        current_low20 = float(
            current_row["LOW20"]
        )

        current_high20 = float(
            current_row["HIGH20"]
        )


        future_low = float(
            future["Low"]
            .min()
        )


        future_high = float(
            future["High"]
            .max()
        )


        if future_low < current_low20:

            break_low20_weight += (
                weight
            )


        if future_high > current_high20:

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


    # =====================================================
    # 为了保证三方向加起来严格100，
    # 震荡用剩余值。
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


    weighted_avg_return = (

        weighted_return_sum
        / total_weight

    )


    median_return = float(

        pd.Series(
            future_returns
        )
        .median()

    )


    # =====================================================
    # 判断最高概率方向
    # =====================================================

    directions = {

        "上涨": up_pct,

        "震荡": sideways_pct,

        "下跌": down_pct

    }


    most_likely = max(

        directions,

        key=directions.get

    )


    return {

        "horizon_days": horizon,

        "sample_size": len(
            selected
        ),

        "method":
            "历史相似状态加权频率",

        "up_pct": up_pct,

        "sideways_pct":
            sideways_pct,

        "down_pct":
            down_pct,

        "most_likely":
            most_likely,

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
# 整理输出
# =========================================================

def build_result(
    name,
    symbol,
    source,
    df
):

    # =====================================================
    # 计算全部指标
    # =====================================================

    df = calculate_indicators(
        df
    )


    # =====================================================
    # MA200 + 历史概率至少需要较长数据
    # =====================================================

    if len(df) < 320:

        raise ValueError(
            f"{name} 长期历史数据不足320个交易日"
        )


    latest = df.iloc[-1]

    previous = df.iloc[-2]


    # =====================================================
    # 检查关键长期指标
    # =====================================================

    required_latest = [

        "MA200",
        "HIGH252",
        "DRAWDOWN_52W",
        "DEV_MA200",
        "RET20"

    ]


    for field in required_latest:

        if pd.isna(
            latest[field]
        ):

            raise ValueError(
                f"{name} 无法计算长期指标 {field}"
            )


    # =====================================================
    # 三套独立判断
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


    scenarios = (
        calculate_historical_scenarios(
            df
        )
    )


    # =====================================================
    # 最新行情
    # =====================================================

    close = float(
        latest["Close"]
    )


    prev_close = float(
        previous["Close"]
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
    # 60日图
    # =====================================================

    history = []


    for index, row in (
        df
        .tail(60)
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

            "boll_upper":
                (
                    round(
                        float(
                            row[
                                "BOLL_UPPER"
                            ]
                        ),
                        2
                    )

                    if pd.notna(
                        row[
                            "BOLL_UPPER"
                        ]
                    )

                    else None
                ),

            "boll_mid":
                (
                    round(
                        float(
                            row[
                                "BOLL_MID"
                            ]
                        ),
                        2
                    )

                    if pd.notna(
                        row[
                            "BOLL_MID"
                        ]
                    )

                    else None
                ),

            "boll_lower":
                (
                    round(
                        float(
                            row[
                                "BOLL_LOWER"
                            ]
                        ),
                        2
                    )

                    if pd.notna(
                        row[
                            "BOLL_LOWER"
                        ]
                    )

                    else None
                )

        })


    # =====================================================
    # 输出
    # =====================================================

    result = {

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
        # 最新行情
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
                    latest["RSI14"]
                ),
                2
            ),

        "macd_dif":
            round(
                float(
                    latest["DIF"]
                ),
                2
            ),

        "macd_dea":
            round(
                float(
                    latest["DEA"]
                ),
                2
            ),

        "macd_hist":
            round(
                float(
                    latest["MACD"]
                ),
                2
            ),


        # =================================================
        # 区间
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
        # 短期技术状态
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
        # 为兼容当前网页
        #
        # 暂时保留旧字段。
        #
        # 下一步修改网页后可不再使用。
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
        # 历史相似情境
        # =================================================

        "scenario_probability":
            scenarios,


        # =================================================
        # 说明
        # =================================================

        "valuation_note":
            (
                "当前长期配置吸引力为价格型代理评分，"
                "尚未接入PE、PB、盈利收益率等基本面估值数据。"
            ),


        # =================================================
        # 60日图
        # =================================================

        "history":
            history

    }


    return result


# =========================================================
# Yahoo Finance
#
# 美股指数获取10年历史数据
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
# 请求约1500个交易日，
# 用于MA200、52周回撤和历史情境分析。
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


    result = response.json()


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
            f"腾讯上证50长期K线不足320日，实际 {len(klines)} 日"
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


        data = get_yahoo_history(

            "上证50",

            "000016.SS"

        )


        data["symbol"] = (
            "000016.SH"
        )


        return data


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
            "2.0-value-allocation",

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
    # 纳指100 / 标普500
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

                    item["name"],

                    item["symbol"]

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
                    item["name"],

                "symbol":
                    item["symbol"],

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

            indent=2

        )


    print(
        "\n======================================"
    )

    print(
        "INDEX RADAR Strategy 2.0 更新完成"
    )

    print(
        "长期配置吸引力 + 市场温度 + 历史相似概率"
    )

    print(
        "======================================"
    )


    # =====================================================
    # 日志只打印摘要
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
                data["error"]
            )

            continue


        print(
            "close:",
            data["close"]
        )

        print(
            "allocation:",
            data["allocation_score"],
            data["allocation_state"]
        )

        print(
            "temperature:",
            data["market_temperature"],
            data["temperature_state"]
        )

        print(
            "technical:",
            data["technical_score"],
            data["technical_state"]
        )

        print(
            "drawdown52w:",
            data["drawdown_52w_pct"]
        )

        print(
            "dev_ma200:",
            data["dev_ma200_pct"]
        )


        if data[
            "scenario_probability"
        ]:

            p = data[
                "scenario_probability"
            ]

            print(
                "20日概率:",
                f"上涨 {p['up_pct']}%",
                f"震荡 {p['sideways_pct']}%",
                f"下跌 {p['down_pct']}%"
            )


# =========================================================
# 程序入口
# =========================================================

if __name__ == "__main__":

    main()
