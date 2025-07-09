import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt
import requests

# 设置环境变量
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 股票列表
stock_list = ["5255.KL", "0209.KL"]

def fetch_stock_data(symbol):
    print(f"📈 抓取 {symbol} 的数据...")
    df = yf.download(symbol, period="3mo", interval="1d", group_by="column")
    if df.empty:
        return None
    df.dropna(inplace=True)

    # 技术指标
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()

    return df

def analyze(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    summary = ""
    macd_cross = latest["MACD_12_26_9"] > latest["MACDs_12_26_9"] and prev["MACD_12_26_9"] < prev["MACDs_12_26_9"]
    rsi_value = latest["RSI_14"]

    if macd_cross:
        summary += "🟢 MACD 金叉，或有上升动能。\n"
    if rsi_value > 70:
        summary += "🔴 RSI 超买，可能回调。\n"
    elif rsi_value < 30:
        summary += "🔵 RSI 超卖，可能反弹。\n"

    return summary.strip()

def draw_chart(symbol, df):
    plt.figure(figsize=(10, 4))
    df.tail(30)["Close"].plot(label="收盘价", color="blue")
    df.tail(30)["MA5"].plot(label="MA5", linestyle="--", color="orange")
    df.tail(30)["MA20"].plot(label="MA20", linestyle="--", color="green")
    plt.title(f"{symbol} 最近走势")
    plt.legend()
    plt.tight_layout()

    chart_path = f"charts/{symbol}_chart.png"
    os.makedirs("charts", exist_ok=True)
    plt.savefig(chart_path)
    plt.close()
    return chart_path

def send_telegram_message(text, image_path=None):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}

    if image_path and os.path.exists(image_path):
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        with open(image_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": TG_CHAT_ID, "caption": text}
            response = requests.post(url, data=data, files=files)
    else:
        response = requests.post(url, data=data)
    
    if not response.ok:
        print("❌ 发送失败：", response.text)

def ask_deepseek(message):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个专业股票分析师，使用简短中文回复。"},
            {"role": "user", "content": message}
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=data)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ DeepSeek API 错误：{e}"

def generate_report(symbol, df):
    latest = df.iloc[-1]
    open_price = latest["Open"]
    close_price = latest["Close"]
    change = close_price - open_price
    percent = (change / open_price) * 100 if open_price != 0 else 0
    emoji = "📈" if change > 0 else "📉" if change < 0 else "➖"

    summary = f"📊 {symbol} 股票简报\n"
    summary += f"开市价：RM {open_price:.3f}\n"
    summary += f"收市价：RM {close_price:.3f}\n"
    summary += f"涨跌：{emoji} {'上涨' if change > 0 else '下跌' if change < 0 else '无涨跌'} RM {abs(change):.3f}（{abs(percent):.2f}%）\n\n"

    summary += analyze(df) + "\n\n"

    # DeepSeek
    ai_prompt = f"股票代码 {symbol} 今日收盘价 RM{close_price:.3f}，开盘价 RM{open_price:.3f}，你怎么看？"
    ai_response = ask_deepseek(ai_prompt)
    summary += f"🤖 DeepSeek 分析：\n{ai_response}"

    return summary

# 主程序
for symbol in stock_list:
    df = fetch_stock_data(symbol)
    if df is None:
        continue
    chart_path = draw_chart(symbol, df)
    message = generate_report(symbol, df)
    send_telegram_message(message, chart_path)
