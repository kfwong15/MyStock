import os
import requests
from flask import Flask, request

app = Flask(__name__)

# 从环境变量读取配置（安全）
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# 👇 DeepSeek AI 聊天接口
def ask_deepseek(message):
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.7
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.ok:
        return response.json()["choices"][0]["message"]["content"].strip()
    else:
        return f"⚠️ DeepSeek 请求失败：{response.text}"

# 👇 处理来自 Telegram 的消息
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_msg = data["message"]["text"]

        # 使用 DeepSeek 回应
        reply = ask_deepseek(user_msg)

        # 发回 Telegram
        send_message(chat_id, reply)
    return "OK"

# 👇 用于向 Telegram 发消息
def send_message(chat_id, text):
    url = f"{TG_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

# 👇 启动时自动设置 webhook（可选）
@app.route("/", methods=["GET"])
def index():
    if BOT_TOKEN and WEBHOOK_URL:
        r = requests.get(f"{TG_API}/setWebhook?url={WEBHOOK_URL}/webhook")
        return f"Webhook set: {r.text}"
    return "Bot is running."

# 👇 Render 部署入口
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
