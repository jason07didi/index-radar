import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import yfinance as yf


# =========================
# 美股指数
# =========================

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


# =========================
# 获取 Yahoo Finance 数据
# =========================

def get_yahoo_data(name, symbol):

    print(f"正在获取：{name} ({symbol})")

    ticker = yf.Ticker(symbol)

    df = ticker.history(
        period="10d",
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


# =========================
# 获取上证50
# 东方财富接口
# =========================

def get_sse50_data():

    name = "上证50"
    symbol = "000016"

    print(f"正在获取：{name} ({symbol})")

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    params = {
        "secid": "1.000016",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": "0",
        "end": "20500101",
        "lmt": "10"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/"
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("data"):
        raise ValueError("东方财富未返回上证50数据")

    klines = data["data"].get("klines", [])

    if len(klines) < 2:
        raise ValueError("上证50历史数据不足")

    # 格式：
    # 日期,开盘,收盘,最高,最低,成交量,成交额,...
    latest = klines[-1].split(",")
    previous = klines[-2].split(",")

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


# =========================
# 主程序
# =========================

def main():

    market_data = {
        "updated_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).strftime("%Y-%m-%d %H:%M:%S"),

        "indices": {}
    }


    # -------------------------
    # 上证50
    # -------------------------

    try:

        market_data["indices"]["sse50"] = get_sse50_data()

    except Exception as e:

        print(f"上证50 获取失败：{e}")

        market_data["indices"]["sse50"] = {
            "name": "上证50",
            "symbol": "000016.SH",
            "error": str(e)
        }


    # -------------------------
    # 纳指100 / 标普500
    # -------------------------

    for key, item in US_INDICES.items():

        try:

            market_data["indices"][key] = get_yahoo_data(
                item["name"],
                item["symbol"]
            )

        except Exception as e:

            print(f"{item['name']} 获取失败：{e}")

            market_data["indices"][key] = {
                "name": item["name"],
                "symbol": item["symbol"],
                "error": str(e)
            }


    # =========================
    # 保存 JSON
    # =========================

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


    print("\n行情数据已经写入：data/market.json")

    print(
        json.dumps(
            market_data,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
