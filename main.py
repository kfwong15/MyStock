import os
import datetime
import requests
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
import pandas_ta as ta

# ====== 配置 ======
STOCKS = ["5255.KL", "0209.KL"]
CHART_FOLDER = "charts"
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


# ====== 工具函数 ======
def fetch_stock_data(symbol):
    df = yf.download(symbol, period="3mo", interval="1d")
    df.dropna(inplace=True)

    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()

    df.ta.macd(close="Close", fast=12, slow=26, signal=9, append=True)
    df.ta.rsi(length=14, append=True)

    return df


def draw_chart(df, symbol):
    plt.figure(figsize=(10, 5))
    plt.plot(df["Close"], label="收盘价", color="blue")
    plt.plot(df["MA5"], label="MA5", linestyle="--", color="green")
    plt.plot(df["MA20"], label="MA20", linestyle="--", color="orange")
    plt.title(f"{symbol} 股票走势图")
    plt.legend()
    plt.grid()
    os.makedirs(CHART_FOLDER, exist_ok=True)
    path = f"{CHART_FOLDER}/{symbol.replace('.KL','')}_chart.png"
    plt.savefig(path)
    plt.close()
    return path


def send_telegram_message(text, image_path=None):
    send_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    photo_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"

    if image_path:
        with open(image_path, "rb") as img:
            response = requests.post(
                photo_url,
                data={"chat_id": TG_CHAT_ID, "caption": text},
                files={"photo": img}
            )
    else:
        response = requests.post(
            send_url,
            data={"chat_id": TG_CHAT_ID, "text": text}
        )
    return response.json()


def get_trend_description(open_price, close_price):
    diff = close_price - open_price
    pct = (diff / open_price) * 100
    if diff > 0:
        return f"📈 上涨 RM {diff:.3f}（{pct:.2f}%）"
    elif diff < 0:
        return f"📉 下跌 RM {abs(diff):.3f}（{abs(pct):.2f}%）"
    else:
        return f"➖ 无涨跌 RM {diff:.3f}（0.00%）"


def ask_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key 未设置"

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位马来西亚股票分析师"},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        res = requests.post(url, json=data, headers=headers, timeout=15)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ DeepSeek API 错误：{str(e)}"


# ====== 主程序 ======
for symbol in STOCKS:
    print(f"📈 抓取 {symbol} 的数据...")
    df = fetch_stock_data(symbol)
    latest = df.iloc[-1]
    open_price = latest["Open"]
    close_price = latest["Close"]
    trend = get_trend_description(open_price, close_price)

    ma5 = latest["MA5"]
    ma20 = latest["MA20"]
    rsi = latest["RSI_14"]
    macd = latest["MACD_12_26_9"]
    signal = latest["MACDs_12_26_9"]

    tips = []

    if close_price > ma20:
        tips.append("⚠️ 当前股价已上穿 MA20，有短期上升动能。")
    if macd > signal:
        tips.append("🟢 MACD 金叉，或有上升动能。")
    if rsi > 70:
        tips.append("📶 RSI > 70，超买区，或将回调。")
    elif rsi < 30:
        tips.append("📉 RSI < 30，超卖区，或有反弹机会。")

    prompt = f"请分析 {symbol} 股票当前走势（开盘价 {open_price:.3f}, 收盘价 {close_price:.3f}, MA20 {ma20:.3f}, RSI {rsi:.1f}, MACD {macd:.3f}）并给出明日操作建议。"
    deepseek_summary = ask_deepseek(prompt)

    message = f"""📊 {symbol} 股票简报
开市价：RM {open_price:.3f}
收市价：RM {close_price:.3f}
涨跌：{trend}

{chr(10).join(tips)}

🤖 DeepSeek 分析：
{deepseek_summary}
"""

    chart_path = draw_chart(df, symbol)
    print("✅ 图表已生成：", chart_path)

    result = send_telegram_message(message, chart_path)
    if result.get("ok"):
        print("✅ 消息已发送至 Telegram")
    else:
        print("❌ 发送失败：", result)
