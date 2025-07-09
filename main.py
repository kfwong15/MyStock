import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import numpy as np
import pytz
from datetime import datetime, timedelta
import time
import re
import json
import traceback
from bs4 import BeautifulSoup

# ========== 配置 ==========
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 处理股票列表
stock_list_str = os.getenv("STOCK_LIST", "5255,0209")
STOCK_LIST = [s.strip().upper() for s in stock_list_str.split(",") if s.strip()]

# 如果没有股票列表，使用默认值
if not STOCK_LIST:
    STOCK_LIST = ["5255", "0209"]

CHART_DIR = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# 设置马来西亚时区
MYT = pytz.timezone('Asia/Kuala_Lumpur')

# ========== 工具函数 ==========
def fetch_data(symbol, retries=3):
    """获取股票数据，使用Bursa Malaysia官方数据源"""
    if not symbol or not re.match(r"^[0-9]{4}$", symbol):
        print(f"⚠️ 无效的股票代码: {symbol}")
        return pd.DataFrame()
    
    # 尝试使用Bursa Malaysia API获取数据
    df = fetch_bursa_malaysia_data(symbol, retries)
    if not df.empty:
        return df
    
    return pd.DataFrame()

def fetch_bursa_malaysia_data(symbol, retries=3):
    """使用Bursa Malaysia API获取股票数据"""
    for attempt in range(retries):
        try:
            print(f"🔍 [Bursa Malaysia] 获取 {symbol} 数据 (尝试 {attempt+1}/{retries})...")
            
            # 获取股票详情
            detail_url = f"https://www.bursamalaysia.com/market_information/equities_prices?stock_code={symbol}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            }
            
            # 获取当前价格数据
            response = requests.get(detail_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取公司名称
            company_name = soup.find('h1', class_='stock-profile').text.strip() if soup.find('h1', class_='stock-profile') else symbol
            
            # 提取当前价格数据
            price_table = soup.find('table', class_='table-price')
            if not price_table:
                print(f"⚠️ [Bursa Malaysia] {symbol} 未找到价格表格")
                continue
                
            rows = price_table.find_all('tr')
            price_data = {}
            for row in rows:
                cols = row.find_all('td')
                if len(cols) == 2:
                    key = cols[0].text.strip().replace(':', '')
                    value = cols[1].text.strip()
                    price_data[key] = value
            
            # 获取历史数据
            history_url = f"https://www.bursamalaysia.com/market_information/equities_prices/historical_stock_prices?stock_code={symbol}"
            response = requests.get(history_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            history_table = soup.find('table', class_='table-price')
            if not history_table:
                print(f"⚠️ [Bursa Malaysia] {symbol} 未找到历史数据表格")
                continue
                
            # 解析历史数据
            history_rows = history_table.find_all('tr')[1:]  # 跳过表头
            history_data = []
            for row in history_rows:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    date_str = cols[0].text.strip()
                    open_price = float(cols[1].text.strip().replace(',', ''))
                    high_price = float(cols[2].text.strip().replace(',', ''))
                    low_price = float(cols[3].text.strip().replace(',', ''))
                    close_price = float(cols[4].text.strip().replace(',', ''))
                    volume = int(cols[5].text.strip().replace(',', ''))
                    
                    history_data.append({
                        'Date': pd.to_datetime(date_str),
                        'Open': open_price,
                        'High': high_price,
                        'Low': low_price,
                        'Close': close_price,
                        'Volume': volume
                    })
            
            # 创建DataFrame
            df = pd.DataFrame(history_data)
            
            # 添加公司名称作为元数据
            df.attrs['company_name'] = company_name
            
            if not df.empty:
                df.set_index('Date', inplace=True)
                print(f"✅ [Bursa Malaysia] 成功获取 {symbol} 数据 ({len(df)} 条记录)")
                return df
            else:
                print(f"⚠️ [Bursa Malaysia] {symbol} 返回空数据")
                
        except Exception as e:
            print(f"⚠️ [Bursa Malaysia] 获取 {symbol} 数据失败: {str(e)}")
            traceback.print_exc()
            time.sleep(2)  # 等待后重试
    
    return pd.DataFrame()

def compute_indicators(df):
    """计算技术指标"""
    if df.empty or len(df) < 5:
        print(f"⚠️ 数据不足 ({len(df)} 条)，无法计算指标")
        return df
        
    # 移动平均线
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    
    # RSI 计算
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    
    with np.errstate(divide='ignore', invalid='ignore'):
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, np.nan)
        df["RSI"] = np.where(~np.isnan(rs), 100 - (100 / (1 + rs)), 50)
    
    # MACD 计算
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    
    return df

def draw_chart(symbol, df):
    """绘制股票图表"""
    if df.empty or len(df) < 5:
        print(f"⚠️ 无法为 {symbol} 绘制图表: 数据不足")
        return None
        
    plt.figure(figsize=(10, 6))
    
    # 自适应显示天数
    days = min(60, len(df))
    tail_df = df.tail(days)
    
    # 价格曲线
    plt.plot(tail_df.index, tail_df["Close"], label="收盘价", linewidth=2, color="#1f77b4")
    
    # 移动平均线
    if "MA5" in df and not df["MA5"].isnull().all():
        plt.plot(tail_df.index, tail_df["MA5"], label="MA5", linestyle="--", color="orange")
    if "MA20" in df and not df["MA20"].isnull().all():
        plt.plot(tail_df.index, tail_df["MA20"], label="MA20", linestyle="-.", color="red")
    
    # 格式化日期
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d', tz=MYT))
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    
    # 获取公司名称用于标题
    company_name = df.attrs.get('company_name', symbol)
    
    plt.title(f"{company_name} ({symbol}) {days}日走势", fontsize=14)
    plt.xlabel("日期", fontsize=10)
    plt.ylabel("价格 (RM)", fontsize=10)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    path = f"{CHART_DIR}/{symbol}_chart.png"
    plt.savefig(path, dpi=100, bbox_inches='tight')
    plt.close()
    print(f"📊 已生成 {symbol} 图表: {path}")
    return path

def ask_deepseek(prompt):
    """调用DeepSeek API获取分析"""
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key 未设置"
    
    print(f"🤖 正在获取AI分析: {prompt[:100]}...")
    try:
        res = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system", 
                        "content": "你是有经验的马来西亚股票分析师，提供简洁的技术分析，使用中文回复。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 400
            },
            timeout=25
        )
        res.raise_for_status()
        data = res.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "❌ API响应格式异常")
        print(f"✅ 获取到AI分析: {content[:100]}...")
        return content
    except requests.exceptions.Timeout:
        return "❌ API请求超时"
    except Exception as e:
        return f"❌ API错误: {str(e)}"

def send_to_telegram(text, img_path=None):
    """发送消息到Telegram"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram凭证未设置")
        return
        
    try:
        print(f"📤 正在发送消息到Telegram...")
        if img_path and os.path.exists(img_path):
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
            with open(img_path, "rb") as pic:
                files = {"photo": pic}
                data = {"chat_id": TG_CHAT_ID, "caption": text[:1000], "parse_mode": "Markdown"}
                response = requests.post(url, data=data, files=files, timeout=15)
                print(f"📷 已发送带图消息 (状态: {response.status_code})")
        else:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
            data = {"chat_id": TG_CHAT_ID, "text": text[:4000], "parse_mode": "Markdown"}
            response = requests.post(url, json=data, timeout=10)
            print(f"💬 已发送文本消息 (状态: {response.status_code})")
    except Exception as e:
        print(f"⚠️ Telegram发送失败: {str(e)}")

def analyze_stock(symbol):
    """分析单只股票并返回报告内容和图表路径"""
    if not symbol:
        return "⚠️ 股票代码为空，跳过分析", None
        
    print(f"\n{'='*40}")
    print(f"📈 开始分析 {symbol}")
    print(f"{'='*40}")
    
    try:
        df = fetch_data(symbol)
        if df.empty:
            return f"⚠️ 找不到 {symbol} 的数据", None

        df = compute_indicators(df)
        
        if len(df) < 2:
            return f"⚠️ {symbol} 数据不足，无法分析", None
            
        # 获取最新数据
        today = df.iloc[-1]
        yesterday = df.iloc[-2] if len(df) >= 2 else today
        
        # 基础价格数据
        open_p = today["Open"]
        close_p = today["Close"]
        high_p = today["High"]
        low_p = today["Low"]
        diff = close_p - open_p
        pct = (diff / open_p) * 100 if open_p != 0 else 0
        trend = "📈 上涨" if diff > 0 else "📉 下跌" if diff < 0 else "➖ 平盘"
        last_trade_date = today.name.strftime('%Y-%m-%d')
        volume = today["Volume"] if "Volume" in today else 0
        
        # 生成技术信号
        signals = []
        
        # MACD 信号
        if all(col in df.columns for col in ["MACD", "MACD_SIGNAL"]):
            macd_val = today.get("MACD", 0)
            signal_val = today.get("MACD_SIGNAL", 0)
            
            if macd_val > signal_val and yesterday.get("MACD", 0) <= yesterday.get("MACD_SIGNAL", 0):
                signals.append("🟢 MACD金叉 - 潜在上涨信号")
            elif macd_val < signal_val and yesterday.get("MACD", 0) >= yesterday.get("MACD_SIGNAL", 0):
                signals.append("🔴 MACD死叉 - 潜在下跌信号")
        
        # RSI 信号
        if "RSI" in df.columns:
            rsi_val = today.get("RSI", 50)
            if rsi_val > 70:
                signals.append(f"🔴 RSI超买 ({rsi_val:.1f})")
            elif rsi_val < 30:
                signals.append(f"🟢 RSI超卖 ({rsi_val:.1f})")
        
        # 均线信号
        if "MA5" in df.columns and "MA20" in df.columns:
            ma5 = today.get("MA5", 0)
            ma20 = today.get("MA20", 0)
            
            if ma5 > ma20 and yesterday.get("MA5", 0) <= yesterday.get("MA20", 0):
                signals.append("🟢 MA5上穿MA20 - 短期看涨")
            elif ma5 < ma20 and yesterday.get("MA5", 0) >= yesterday.get("MA20", 0):
                signals.append("🔴 MA5下穿MA20 - 短期看跌")
        
        # 获取公司名称
        company_name = df.attrs.get('company_name', symbol)
        
        # 构建AI提示
        prompt = (
            f"作为专业股票分析师，请用中文简洁分析 {company_name} ({symbol})："
            f"最后交易日 {last_trade_date}，开盘价 RM{open_p:.3f}，最高价 RM{high_p:.3f}，"
            f"最低价 RM{low_p:.3f}，收盘价 RM{close_p:.3f}（{trend} {abs(diff):.3f}，涨跌幅 {pct:.2f}%），"
            f"成交量 {volume:,}。"
        )
        
        # 添加技术指标
        if "MA5" in df.columns:
            prompt += f" 5日均线(MA5)=RM{today['MA5']:.3f}, 20日均线(MA20)=RM{today['MA20']:.3f};"
        if "RSI" in df.columns:
            prompt += f" RSI={today['RSI']:.1f};"
        if "MACD" in df.columns and "MACD_SIGNAL" in df.columns:
            prompt += f" MACD={today['MACD']:.3f}, 信号线={today['MACD_SIGNAL']:.3f}。"
        
        prompt += " 请给出1-2句技术分析结论和操作建议。"
        
        # 获取AI分析
        ai_comment = ask_deepseek(prompt)
        
        # 构建消息
        msg = (
            f"📊 *{company_name} ({symbol}) 股票分析报告*\n"
            f"• 最后交易日: `{last_trade_date}`\n"
            f"• 开盘价: `RM {open_p:.3f}`\n"
            f"• 最高价: `RM {high_p:.3f}`\n"
            f"• 最低价: `RM {low_p:.3f}`\n"
            f"• 收盘价: `RM {close_p:.3f}`\n"
            f"• 涨跌幅: {trend} `RM {abs(diff):.3f}` ({pct:.2f}%)\n"
            f"• 成交量: `{volume:,}`\n"
        )
        
        # 添加技术信号
        if signals:
            msg += "\n📈 *技术信号*:\n" + "\n".join([f"• {s}" for s in signals]) + "\n"
        
        msg += f"\n🤖 *AI分析*:\n{ai_comment}\n\n_更新于: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M MYT')}_"
        
        # 生成图表
        chart_path = draw_chart(symbol, df)
        
        return msg, chart_path
        
    except Exception as e:
        error_msg = f"⚠️ 分析 {symbol} 时出错: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return error_msg, None

# ========== 主执行逻辑 ==========
def main():
    print(f"\n{'='*50}")
    print(f"🚀 开始股票分析 - {datetime.now(MYT).strftime('%Y-%m-%d %H:%M MYT')}")
    print(f"📋 分析 {len(STOCK_LIST)} 只股票: {', '.join(STOCK_LIST)}")
    print(f"{'='*50}\n")
    
    for symbol in STOCK_LIST:
        msg, chart_path = analyze_stock(symbol)
        if msg:
            send_to_telegram(msg, chart_path)
        time.sleep(5)  # 避免API限流
    
    print(f"\n{'='*50}")
    print(f"✅ 分析完成! 已处理 {len(STOCK_LIST)} 只股票")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
