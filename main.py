import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import os
import numpy as np
from textblob import TextBlob
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# 配置参数
bot_token = os.getenv("TG_BOT_TOKEN")
chat_id = os.getenv("TG_CHAT_ID")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# 技术指标计算
def calculate_technical_indicators(df):
    # 移动平均线
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA50"] = df["Close"].rolling(window=50).mean()
    
    # RSI
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # 布林带
    df["MiddleBand"] = df["Close"].rolling(window=20).mean()
    df["UpperBand"] = df["MiddleBand"] + 2 * df["Close"].rolling(window=20).std()
    df["LowerBand"] = df["MiddleBand"] - 2 * df["Close"].rolling(window=20).std()
    
    # 交易量分析
    df["VolumeMA20"] = df["Volume"].rolling(window=20).mean()
    df["VolumeChange"] = (df["Volume"] / df["VolumeMA20"] - 1) * 100
    
    return df

# 生成图表
def generate_stock_chart(stock, hist_df):
    plt.figure(figsize=(14, 10))
    
    # 价格图表
    ax1 = plt.subplot2grid((10, 1), (0, 0), rowspan=6, colspan=1)
    ax1.plot(hist_df["Close"], label="收盘价", color="black", linewidth=1.5)
    ax1.plot(hist_df["MA5"], label="5日均线", color="blue", linestyle="--")
    ax1.plot(hist_df["MA20"], label="20日均线", color="red", linestyle="--")
    ax1.plot(hist_df["MA50"], label="50日均线", color="green", linestyle="--")
    ax1.plot(hist_df["UpperBand"], label="布林带上轨", color="orange", alpha=0.5)
    ax1.plot(hist_df["LowerBand"], label="布林带下轨", color="orange", alpha=0.5)
    ax1.fill_between(hist_df.index, hist_df["LowerBand"], hist_df["UpperBand"], color="orange", alpha=0.1)
    
    # 标记关键点
    last_close = hist_df["Close"].iloc[-1]
    if last_close > hist_df["UpperBand"].iloc[-1]:
        ax1.scatter(hist_df.index[-1], last_close, color="red", s=100, marker="^", label="突破上轨")
    elif last_close < hist_df["LowerBand"].iloc[-1]:
        ax1.scatter(hist_df.index[-1], last_close, color="green", s=100, marker="v", label="突破下轨")
    
    ax1.set_title(f"{stock} - 技术分析", fontsize=16)
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle="--", alpha=0.7)
    
    # RSI图表
    ax2 = plt.subplot2grid((10, 1), (6, 0), rowspan=2, colspan=1, sharex=ax1)
    ax2.plot(hist_df["RSI"], label="RSI", color="purple")
    ax2.axhline(70, color="red", linestyle="--", alpha=0.7)
    ax2.axhline(30, color="green", linestyle="--", alpha=0.7)
    ax2.fill_between(hist_df.index, 30, 70, color="gray", alpha=0.1)
    ax2.set_ylabel("RSI")
    ax2.legend(loc="upper left")
    ax2.grid(True, linestyle="--", alpha=0.5)
    
    # 交易量图表
    ax3 = plt.subplot2grid((10, 1), (8, 0), rowspan=2, colspan=1, sharex=ax1)
    ax3.bar(hist_df.index, hist_df["Volume"], color=["green" if close >= open else "red" 
           for open, close in zip(hist_df["Open"], hist_df["Close"])], alpha=0.7)
    ax3.plot(hist_df["VolumeMA20"], label="20日平均量", color="blue")
    ax3.set_ylabel("交易量")
    ax3.grid(True, linestyle="--", alpha=0.5)
    
    plt.tight_layout()
    filename = f"charts/{stock.replace('.KL', '')}_chart.png"
    plt.savefig(filename)
    plt.close()
    return filename

# 新闻情感分析
def analyze_news_sentiment(news_items):
    if not news_items:
        return "📰 今日相关新闻：暂无相关新闻。", ""
    
    news_text = "\n📰 今日相关新闻："
    sentiment_scores = []
    
    for news in news_items[:3]:
        title = news.get("title", "无标题")
        source = news.get("publisher", "来源未知")
        link = news.get("link", "#")
        
        # 情感分析
        analysis = TextBlob(title)
        sentiment = "👍" if analysis.sentiment.polarity > 0.1 else "👎" if analysis.sentiment.polarity < -0.1 else "➖"
        sentiment_scores.append(analysis.sentiment.polarity)
        
        news_text += f"\n• {sentiment} [{source}] <a href='{link}'>{title}</a>"
    
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
    sentiment_summary = f"\n\n📊 新闻情绪: {'积极' if avg_sentiment > 0.1 else '消极' if avg_sentiment < -0.1 else '中性'} ({avg_sentiment:.2f})"
    
    return news_text, sentiment_summary

# 生成HTML报告
def generate_html_report(stock, data, news_text, sentiment_summary, chart_path):
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    stock_name = stock.replace(".KL", "")
    
    html_content = f"""
    <html>
    <head>
        <title>{stock_name} 股票报告</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background-color: #f0f0f0; padding: 15px; border-radius: 8px; }}
            .metrics {{ display: flex; justify-content: space-between; margin: 20px 0; }}
            .metric-box {{ 
                background-color: {'#e6f7e6' if data['pct_change'] > 0 else '#ffe6e6'};
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                width: 30%;
                text-align: center;
            }}
            .chart {{ text-align: center; margin: 20px 0; }}
            .news {{ background-color: #f9f9f9; padding: 15px; border-radius: 8px; }}
            .indicator {{ margin: 10px 0; padding: 10px; border-left: 4px solid #4CAF50; }}
            .critical {{ border-left-color: #f44336; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{stock_name} 股票分析报告</h1>
            <p>生成时间: {report_date}</p>
        </div>
        
        <div class="metrics">
            <div class="metric-box">
                <h3>今日价格</h3>
                <p>开盘: RM {data['open_price']:.3f}</p>
                <p>收盘: RM {data['close_price']:.3f}</p>
                <p>涨跌: {'📈' if data['change'] > 0 else '📉'} RM {data['change']:.3f} ({data['pct_change']:.2f}%)</p>
            </div>
            
            <div class="metric-box">
                <h3>技术指标</h3>
                <p>RSI: {data['rsi']:.2f} {'(超买)' if data['rsi'] > 70 else '(超卖)' if data['rsi'] < 30 else ''}</p>
                <p>成交量变化: {data['volume_change']:.2f}%</p>
                <p>布林带位置: {data['bollinger_position']}</p>
            </div>
            
            <div class="metric-box">
                <h3>移动平均线</h3>
                <p>MA5: RM {data['ma5']:.3f}</p>
                <p>MA20: RM {data['ma20']:.3f}</p>
                <p>MA50: RM {data['ma50']:.3f}</p>
            </div>
        </div>
        
        <div class="chart">
            <img src="cid:stock_chart" alt="Stock Chart" style="max-width: 100%;">
        </div>
        
        <div class="analysis">
            <h2>趋势分析</h2>
            <p>{data['trend_icon']} {data['reason']}</p>
            
            <div class="indicator {'critical' if '金叉' in data['trend_advice'] or '死叉' in data['trend_advice'] else ''}">
                <h3>交易信号</h3>
                <p>{data['trend_advice']}</p>
            </div>
            
            <div class="indicator">
                <h3>关键价格水平</h3>
                <p>支撑位: RM {data['support_level']:.3f}</p>
                <p>阻力位: RM {data['resistance_level']:.3f}</p>
            </div>
        </div>
        
        <div class="news">
            <h2>市场新闻</h2>
            {news_text}
            {sentiment_summary}
        </div>
    </body>
    </html>
    """
    
    # 保存HTML文件
    os.makedirs("reports", exist_ok=True)
    html_path = f"reports/{stock_name}_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return html_path

# 发送邮件报告
def send_email_report(subject, html_path, chart_path):
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_RECIPIENT:
        print("⚠️ 邮件发送失败：缺少邮件配置")
        return
    
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_RECIPIENT
    
    # 添加HTML内容
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    msg.attach(MIMEText(html_content, "html"))
    
    # 添加图表
    with open(chart_path, "rb") as img:
        img_data = img.read()
        image = MIMEImage(img_data)
        image.add_header("Content-ID", "<stock_chart>")
        msg.attach(image)
    
    # 发送邮件
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, EMAIL_RECIPIENT, msg.as_string())
        print(f"✅ 邮件已发送: {subject}")
    except Exception as e:
        print(f"❌ 邮件发送失败: {str(e)}")

# 发送Telegram图片
def send_telegram_photo(photo_path, caption=""):
    if not bot_token or not chat_id:
        print("⚠️ Telegram发送失败：缺少配置")
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with open(photo_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {"chat_id": chat_id, "caption": caption}
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                print(f"✅ Telegram图片已发送：{photo_path}")
            else:
                print(f"❌ Telegram发送失败：{response.text}")
    except Exception as e:
        print(f"❌ Telegram图片发送错误：{str(e)}")

# 发送Telegram消息
def send_telegram_message(message):
    if not bot_token or not chat_id:
        print("⚠️ Telegram消息发送失败：缺少配置")
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ Telegram消息发送成功")
        else:
            print(f"❌ Telegram消息发送失败: {response.text}")
    except Exception as e:
        print(f"❌ Telegram消息发送错误：{str(e)}")

# 主函数
def main():
    # 创建目录
    os.makedirs("charts", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    
    # 自选股列表
    my_stocks = ["5255.KL", "0209.KL"]
    
    for stock in my_stocks:
        try:
            print(f"📈 抓取 {stock} 的数据...")
            
            # 获取历史数据（60天）
            hist_df = yf.download(stock, period="60d", interval="1d")
            if hist_df.empty:
                print(f"⚠️ 未获取到 {stock} 的数据")
                continue
                
            # 计算技术指标
            hist_df = calculate_technical_indicators(hist_df)
            
            # 获取最新数据
            latest = hist_df.iloc[[-1]]
            prev_day = hist_df.iloc[[-2]] if len(hist_df) > 1 else None
            
            # 基础价格数据
            open_price = float(latest["Open"].iloc[0])
            close_price = float(latest["Close"].iloc[0])
            high_price = float(latest["High"].iloc[0])
            low_price = float(latest["Low"].iloc[0])
            volume = int(latest["Volume"].iloc[0])
            
            change = close_price - open_price
            pct_change = (change / open_price) * 100 if open_price else 0.0
            
            # 技术指标数据
            rsi = float(latest["RSI"].iloc[0]) if pd.notna(latest["RSI"].iloc[0]) else 0.0
            volume_change = float(latest["VolumeChange"].iloc[0]) if pd.notna(latest["VolumeChange"].iloc[0]) else 0.0
            ma5 = float(latest["MA5"].iloc[0])
            ma20 = float(latest["MA20"].iloc[0])
            ma50 = float(latest["MA50"].iloc[0])
            
            # 布林带位置分析
            if close_price > float(latest["UpperBand"].iloc[0]):
                bollinger_position = "突破上轨 (超买)"
            elif close_price < float(latest["LowerBand"].iloc[0]):
                bollinger_position = "突破下轨 (超卖)"
            else:
                bollinger_position = "区间内"
            
            # 关键价格水平
            resistance_level = max(hist_df["High"].tail(20))
            support_level = min(hist_df["Low"].tail(20))
            
            # 涨跌趋势分析
            if change > 0:
                trend_icon = "📈 上涨"
                reason = "可能受到市场乐观或业绩预期带动。"
            elif change < 0:
                trend_icon = "📉 下跌"
                reason = "可能受到市场回调或负面情绪影响。"
            else:
                trend_icon = "➖ 无涨跌"
                reason = "今日股价稳定，缺乏波动。"
            
            # 趋势建议
            trend_advice = ""
            if close_price > ma20:
                trend_advice += "当前股价在20日均线上方，显示中期趋势向上。"
            else:
                trend_advice += "当前股价在20日均线下方，显示中期趋势向下。"
                
            if prev_day is not None:
                prev_ma5 = float(prev_day["MA5"].iloc[0])
                prev_ma20 = float(prev_day["MA20"].iloc[0])
                
                if ma5 > ma20 and prev_ma5 < prev_ma20:
                    trend_advice += " ⚠️ MA5金叉MA20，短线买入信号！"
                elif ma5 < ma20 and prev_ma5 > prev_ma20:
                    trend_advice += " ⚠️ MA5死叉MA20，短线卖出信号！"
                
            if rsi > 70:
                trend_advice += " ⚠️ RSI超买(>70)，警惕回调风险！"
            elif rsi < 30:
                trend_advice += " ⚠️ RSI超卖(<30)，可能有反弹机会！"
                
            if volume_change > 50:
                trend_advice += f" ⚠️ 交易量异常增加({volume_change:.0f}%)，关注资金流向！"
            
            # 获取新闻并分析情感
            try:
                ticker = yf.Ticker(stock)
                news_items = ticker.news
                news_text, sentiment_summary = analyze_news_sentiment(news_items)
            except Exception as e:
                print(f"❌ 新闻获取失败: {str(e)}")
                news_text = "\n📰 今日相关新闻：获取失败。"
                sentiment_summary = ""
            
            # 生成图表
            chart_path = generate_stock_chart(stock, hist_df)
            print(f"✅ 图表已生成：{chart_path}")
            
            # 准备数据
            stock_data = {
                "open_price": open_price,
                "close_price": close_price,
                "change": change,
                "pct_change": pct_change,
                "rsi": rsi,
                "volume_change": volume_change,
                "ma5": ma5,
                "ma20": ma20,
                "ma50": ma50,
                "trend_icon": trend_icon,
                "reason": reason,
                "trend_advice": trend_advice,
                "bollinger_position": bollinger_position,
                "support_level": support_level,
                "resistance_level": resistance_level
            }
            
            # 生成HTML报告
            html_path = generate_html_report(stock, stock_data, news_text, sentiment_summary, chart_path)
            print(f"✅ HTML报告已生成：{html_path}")
            
            # 发送邮件报告
            stock_name = stock.replace(".KL", "")
            send_email_report(f"{stock_name} 股票分析报告", html_path, chart_path)
            
            # 发送Telegram通知
            caption = (
                f"📊 {stock} 股票分析\n"
                f"价格: RM {close_price:.3f} ({'↑' if change > 0 else '↓'} {pct_change:.2f}%)\n"
                f"RSI: {rsi:.1f} {'(超买)' if rsi > 70 else '(超卖)' if rsi < 30 else ''}\n"
                f"关键信号: {trend_advice[:100]}..."
            )
            send_telegram_photo(chart_path, caption)
            
        except Exception as e:
            print(f"❌ 处理 {stock} 时出错: {str(e)}")
            # 发送错误通知
            error_msg = f"⚠️ 股票报告错误: {stock}\n错误详情: {str(e)}"
            send_telegram_message(error_msg)

# 确保这个部分在文件末尾且没有缩进
if __name__ == "__main__":
    main()
