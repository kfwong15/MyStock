import os
import requests
import yfinance as yf
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "default")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# 获取股票信息简报
def get_stock_summary(stock_code):
    try:
        stock = yf.Ticker(stock_code)
        df = stock.history(period="5d")
        if df.empty:
            return f"❌ 无法获取 {stock_code} 的数据"

        latest = df.iloc[-1]
        open_price = latest['Open']
        close_price = latest['Close']
        change = close_price - open_price
        pct = (change / open_price) * 100

        trend = "📈 上涨" if change > 0 else "📉 下跌" if change < 0 else "➖ 无涨跌"
        summary = (
            f"📊 {stock_code} 股票简报\n"
            f"开市价：RM {open_price:.3f}\n"
            f"收市价：RM {close_price:.3f}\n"
            f"涨跌：{trend} RM {change:.3f}（{pct:.2f}%）"
        )

        # DeepSeek AI 分析建议
        suggestion = ask_deepseek_ai(stock_code, summary)
        return summary + "\n\n" + suggestion

    except Exception as e:
        return f"⚠️ 获取失败：{str(e)}"

# DeepSeek AI 调用
def ask_deepseek_ai(stock_code, summary_text):
    prompt = f"以下是股票 {stock_code} 的简报：\n{summary_text}\n请用中文分析这个股票的技术趋势，并给出明日建议。"
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一位资深股票技术分析师。"},
                    {"role": "user", "content": prompt}
                ]
            }
        )
        result = response.json()
        return "🤖 DeepSeek 分析：\n" + result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ DeepSeek API 错误：{str(e)}"

# 接收 Webhook
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "ignored", 200

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/stock"):
        parts = text.split(" ")
        if len(parts) >= 2:
            stock_code = parts[1].upper()
            reply = get_stock_summary(stock_code)
        else:
            reply = "请提供股票代码，例如：/stock 5255.KL"
    elif text.startswith("/start"):
        reply = "欢迎使用📈股票机器人！\n输入 /stock 股票代码 查询行情。"
    else:
        reply = "🤖 指令无效，请输入 /stock 股票代码"

    # 发送回复
    requests.post(TELEGRAM_API, json={
        "chat_id": chat_id,
        "text": reply
    })

    return "ok", 200

@app.route("/")
def root():
    return "✅ Bot is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
