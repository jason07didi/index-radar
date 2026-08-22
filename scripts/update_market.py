import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import yfinance as yf


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
# Yahoo Finance
# 用于纳斯达克100、标普500
# =========================================================

def get_yahoo_data(name, symbol):

    print(f"正在获取：{name} ({symbol})")

    ticker = yf.Ticker(symbol)

    df = ticker.history(
        period="1mo",
        interval="1d",
        auto_adjust=False
    )

    df = df.dropna(subset=["Close"])

    if len(df) < 2:
        raise ValueError(f"{name} 获取的数据不足")

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    close = float(latest["Close"])
    prev_close = float(previous["Close"])

    change = close - prev_close
    change_pct = change / prev_close * 100

    return {
        "name": name,
        "symbol": symbol,
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "close": round(close, 2),
        "previous_close": round(prev_close, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2)
    }


# =========================================================
# 腾讯财经
# 用于上证50
# =========================================================

def get_sse50_tencent():

    name = "上证50"
    code = "sh000016"

    print(f"正在通过腾讯获取：{name} ({code})")

    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    params = {
        "param": f"{code},day,,,20,qfq"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
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
        raise ValueError("腾讯接口没有返回 data")

    if code not in result["data"]:
        raise ValueError("腾讯接口没有返回上证50")

    stock_data = result["data"][code]

    # 普通股票可能返回 qfqday
    # 指数通常返回 day
    klines = (
        stock_data.get("qfqday")
        or stock_data.get("day")
        or []
    )

    if len(klines) < 2:
        raise ValueError("腾讯上证50历史数据不足")

    latest = klines[-1]
    previous = klines[-2]

    # 腾讯K线格式通常为：
    # 日期、开盘、收盘、最高、最低、成交量...
    date = latest[0]

    close = float(latest[2])
    prev_close = float(previous[2])

    change = close - prev_close
    change_pct = change / prev_close * 100

    return {
        "name": name,
        "symbol": "000016.SH",
        "date": date,
        "close": round(close, 2),
        "previous_close": round(prev_close, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2)
    }


# =========================================================
# Yahoo 作为上证50备用数据源
# =========================================================

def get_sse50_yahoo_backup():

    print("腾讯获取失败，尝试 Yahoo 备用源...")

    return get_yahoo_data(
        "上证50",
        "000016.SS"
    )


# =========================================================
# 上证50
# 腾讯优先，Yahoo备用
# =========================================================

def get_sse50_data():

    try:

        data = get_sse50_tencent()

        data["source"] = "Tencent"

        return data

    except Exception as tencent_error:

        print(f"腾讯获取失败：{tencent_error}")

        try:

            data = get_sse50_yahoo_backup()

            data["symbol"] = "000016.SH"
            data["source"] = "Yahoo"

            return data

        except Exception as yahoo_error:

            raise ValueError(
                f"腾讯失败：{tencent_error}; "
                f"Yahoo失败：{yahoo_error}"
            )


# =========================================================
# 主程序
# =========================================================

def main():

    market_data = {

        "updated_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).strftime("%Y-%m-%d %H:%M:%S"),

        "indices": {}
    }


    # -----------------------------------------------------
    # 上证50
    # -----------------------------------------------------

    try:

        market_data["indices"]["sse50"] = get_sse50_data()

    except Exception as e:

        print(f"上证50最终获取失败：{e}")

        market_data["indices"]["sse50"] = {
            "name": "上证50",
            "symbol": "000016.SH",
            "error": str(e)
        }


    # -----------------------------------------------------
    # 纳斯达克100 / 标普500
    # -----------------------------------------------------

    for key, item in US_INDICES.items():

        try:

            data = get_yahoo_data(
                item["name"],
                item["symbol"]
            )

            data["source"] = "Yahoo"

            market_data["indices"][key] = data

        except Exception as e:

            print(f"{item['name']} 获取失败：{e}")

            market_data["indices"][key] = {
                "name": item["name"],
                "symbol": item["symbol"],
                "error": str(e)
            }


    # =====================================================
    # 写入 JSON
    # =====================================================

    output_path = Path("data/market.json")

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


    print("\n======================================")
    print("行情数据已经写入 data/market.json")
    print("======================================")

    print(
        json.dumps(
            market_data,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
