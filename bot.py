import os
import requests
from flask import Flask, request

TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

app = Flask(__name__)

# --- DeepSeek Chat Completion ---
def ask_deepseek(question):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个股票和财经分析专家。"},
            {"role": "user", "content": question}
        ]
    }
    r = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
    return r.json().get("choices", [{}])[0].get("message", {}).get("content", "⚠️ 无法获取 DeepSeek 回答。")

# --- Telegram Bot 接收 Webhook ---
@app.route(f"/webhook", methods=["POST"])
def telegram_webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text.startswith("/ask"):
        question = text.replace("/ask", "").strip()
        if question:
            answer = ask_deepseek(question)
        else:
            answer = "❓ 请提供你想问的问题，例如：/ask 马来西亚股市前景如何？"
        send_telegram_message(chat_id, answer)

    return {"ok": True}

# --- 发信息到 Telegram ---
def send_telegram_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": text})

# --- 本地测试启动 Flask ---
if __name__ == "__main__":
    app.run(debug=True)
