import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf


# 三个指数
INDICES = {
    "sse50": {
        "name": "上证50",
        "symbol": "000016.SS"
    },
    "nasdaq100": {
        "name": "纳斯达克100",
        "symbol": "^NDX"
    },
    "sp500": {
        "name": "标普500",
        "symbol": "^GSPC"
    }
}


def get_index_data(name, symbol):
    print(f"正在获取：{name} ({symbol})")

    ticker = yf.Ticker(symbol)

    # 获取最近10个交易日
    df = ticker.history(
        period="10d",
        interval="1d",
        auto_adjust=False
    )

    # 删除没有收盘价的数据
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


def main():

    market_data = {
        "updated_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "indices": {}
    }

    for key, item in INDICES.items():

        try:
            market_data["indices"][key] = get_index_data(
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

    # 输出位置
    output_path = Path("data/market.json")

    # 确保 data 文件夹存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            market_data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n行情数据已经写入：data/market.json")
    print(json.dumps(market_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
