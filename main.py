import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import json
import os

# =================== 配置 ====================
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 自选股列表
my_stocks = ["5255.KL", "0209.KL"]

# 创建图表目录
os.makedirs("charts", exist_ok=True)

# =================== 函数定义 ====================

# 📤 Telegram 发送图片
def send_telegram_photo(bot_token, chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(photo_path, "rb") as photo_file:
        files = {"photo": photo_file}
        data = {"chat_id": chat_id, "caption": caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 已发送：{photo_path}")
        else:
            print(f"❌ 发送失败：{response.text}")

# 🤖 调用 DeepSeek 分析评论
def ask_deepseek(prompt):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一名股票分析助理，请用简洁方式分析股票表现。"},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        res_json = response.json()
        if "choices" in res_json:
            return res_json["choices"][0]["message"]["content"]
        else:
            return "❌ DeepSeek API 返回无效内容。"
    else:
        return f"❌ DeepSeek API 错误：{response.text}"

# =================== 主逻辑 ====================

for stock in my_stocks:
    print(f"📈 抓取 {stock} 的数据...")
    df = yf.download(stock, period="60d", interval="1d")

    if df.empty:
        print(f"⚠️ 无法获取 {stock} 的数据")
        continue

    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()

    # RSI (14日)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # 当前数据
    latest = df.iloc[-1]
    open_price = float(latest["Open"])
    close_price = float(latest["Close"])
    change = close_price - open_price
    pct_change = (change / open_price) * 100
    ma5 = float(latest["MA5"])
    ma20 = float(latest["MA20"])
    rsi = float(latest["RSI"])
    macd = float(latest["MACD"])
    signal = float(latest["Signal"])

    # 趋势判断
    trend_icon = "➖ 无涨跌"
    if change > 0:
        trend_icon = "📈 上涨"
    elif change < 0:
        trend_icon = "📉 下跌"

    tech_signal = ""
    if rsi > 70:
        tech_signal += "🔴 RSI > 70，超买风险。\n"
    elif rsi < 30:
        tech_signal += "🟢 RSI < 30，可能超卖反弹。\n"

    if macd > signal:
        tech_signal += "🟢 MACD 金叉，或有上升动能。\n"
    elif macd < signal:
        tech_signal += "🔴 MACD 死叉，警惕回调。\n"

    # DeepSeek 评论
    prompt = f"分析股票 {stock}，今日收盘价 RM{close_price:.2f}，涨幅 {pct_change:.2f}%。MA5={ma5:.2f}，MA20={ma20:.2f}，RSI={rsi:.2f}，MACD={macd:.2f}，Signal={signal:.2f}。请简要分析趋势并给出判断建议（用中文）。"
    deepseek_comment = ask_deepseek(prompt)

    # 汇总内容
    caption = (
        f"📊 {stock} 股票简报\n"
        f"开市价：RM {open_price:.3f}\n"
        f"收市价：RM {close_price:.3f}\n"
        f"涨跌：{trend_icon} RM {change:.3f}（{pct_change:.2f}%）\n\n"
        f"{tech_signal}"
        f"\n🤖 DeepSeek 分析：\n{deepseek_comment}"
    )

    # 绘图
    plt.figure(figsize=(12, 6))
    plt.plot(df["Close"], label="收盘价", color="black")
    plt.plot(df["MA5"], label="MA5", color="blue")
    plt.plot(df["MA20"], label="MA20", color="red")
    plt.title(f"{stock} 近60日走势图")
    plt.xlabel("日期")
    plt.ylabel("价格 (RM)")
    plt.legend()
    plt.grid(True)

    chart_path = f"charts/{stock.replace('.KL','')}_chart.png"
    plt.savefig(chart_path)
    plt.close()
    print(f"✅ 图表已生成：{chart_path}")

    send_telegram_photo(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, chart_path, caption)
