import yfinance as yf
import time
from datetime import datetime, timedelta
import csv
import os
import pytz
import pyodbc
import feedparser

# =========================
# 股票清單與公司對照
stocks = [
    "AAPL", "MSFT", "GOOGL", "NVDA",
    "XOM", "CVX", "JPM", "GS",
    "LMT", "BA", "TSLA", "^DJI"
]

company_names = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Google",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "JPM": "JPMorgan",
    "GS": "Goldman Sachs",
    "LMT": "Lockheed Martin",
    "BA": "Boeing",
    "^DJI": "Dow Jones"
}

# =========================
# 設定
stock_interval = 30  # 秒
news_per_stock = 5
eastern = pytz.timezone("US/Eastern")
saved_close_today = set()
today_date = datetime.now().strftime("%Y-%m-%d")

# =========================
# CSV 路徑
def get_csv_filename():
    return f"stock_close_{datetime.now().strftime('%Y-%m-%d')}.csv"

def ensure_csv_file():
    csv_file = get_csv_filename()
    if not os.path.exists(csv_file):
        with open(csv_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["日期", "股票", "收盤價"])
    return csv_file

def get_news_csv():
    return f"stock_news_{datetime.now().strftime('%Y-%m-%d')}.csv"

def ensure_news_csv():
    csv_file = get_news_csv()
    if not os.path.exists(csv_file):
        with open(csv_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["抓取時間", "股票", "標題", "新聞連結", "來源", "摘要"])
    return csv_file

# =========================
# 股價抓取
def get_realtime_price(stock_id):
    stock = yf.Ticker(stock_id)
    try:
        df_min = stock.history(period="1d", interval="1m")
        price = round(df_min["Close"].iloc[-1], 4) if not df_min.empty else "-"
        return price
    except:
        return "-"

def get_daily_close(stock_id):
    stock = yf.Ticker(stock_id)
    try:
        df = stock.history(period="2d")  # 前兩天
        if df.empty or len(df) < 2:
            return "-"
        close_price = round(df["Close"].iloc[-2], 4)  # 前一交易日收盤價
        return close_price
    except:
        return "-"

# =========================
# 判斷美股收盤
def is_us_market_closed():
    now = datetime.now(eastern)
    return now.weekday() < 5 and now.hour >= 16

# =========================
# SQL Server 連線
server = 'linpeichunhappy.database.windows.net'
database = 'stock_project'
username = 'missa'
password = 'Cc12345678'
driver = '{ODBC Driver 18 for SQL Server}'

conn = pyodbc.connect(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
)
cursor = conn.cursor()

# 建表
cursor.execute("""
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='stock_close' AND xtype='U')
CREATE TABLE stock_close (
    date DATE,
    stock_id NVARCHAR(10),
    close_price FLOAT,
    PRIMARY KEY(date, stock_id)
)
""")
cursor.execute("""
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='stock_news' AND xtype='U')
CREATE TABLE stock_news (
    stock_id NVARCHAR(10),
    link NVARCHAR(500) PRIMARY KEY,
    title NVARCHAR(500),
    source NVARCHAR(100),
    snippet NVARCHAR(1000),
    fetch_time DATETIME
)
""")
conn.commit()

# =========================
# 寫入收盤價 (CSV + SQL)
def save_close_price(stock_id, close_price):
    global saved_close_today, today_date
    now_date = datetime.now().strftime("%Y-%m-%d")
    csv_file = ensure_csv_file()

    if now_date != today_date:
        saved_close_today = set()
        today_date = now_date
        csv_file = ensure_csv_file()

    if stock_id in saved_close_today or close_price in ["-","無資料"]:
        return

    close_price = round(float(close_price), 4)

    with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([now_date, stock_id, close_price])

    try:
        cursor.execute("""
        MERGE INTO stock_close AS target
        USING (SELECT ? AS date, ? AS stock_id, ? AS close_price) AS source
        ON target.date = source.date AND target.stock_id = source.stock_id
        WHEN NOT MATCHED THEN
        INSERT (date, stock_id, close_price)
        VALUES (source.date, source.stock_id, source.close_price);
        """, now_date, stock_id, close_price)
        conn.commit()
    except Exception as e:
        print(f"❌ SQL收盤價寫入失敗: {stock_id}, {e}")
    saved_close_today.add(stock_id)

# =========================
# 抓新聞 (RSS)
def fetch_news(stock_id):
    company = company_names.get(stock_id,"")
    if not company:
        return []
    keyword = f"{stock_id} OR {company} stock"
    url = f"https://news.google.com/rss/search?q={keyword}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        news_list = []
        for entry in feed.entries[:5]:
            title = entry.title
            link = entry.link
            source = entry.source.title if hasattr(entry,"source") else ""
            snippet = entry.summary if hasattr(entry,"summary") else ""
            news_list.append({
                "股票": stock_id,
                "標題": title,
                "新聞連結": link,
                "來源": source,
                "摘要": snippet
            })
        return news_list
    except Exception as e:
        print(f"❌ {stock_id} 新聞抓取錯誤: {e}")
        return []

def save_news(news_list):
    if not news_list:
        return
    csv_file = ensure_news_csv()
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        for news in news_list:
            writer.writerow([now_time, news["股票"], news["標題"], news["新聞連結"], news["來源"], news["摘要"]])
            try:
                cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM stock_news WHERE link=?)
                INSERT INTO stock_news (stock_id, link, title, source, snippet, fetch_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """, news["新聞連結"], news["股票"], news["新聞連結"], news["標題"], news["來源"], news["摘要"], now_time)
                conn.commit()
            except Exception as e:
                print(f"❌ SQL新聞寫入失敗: {e}")

# =========================
# Console 顯示
def display_realtime(stock_data_list, news_summary_dict):
    os.system('cls' if os.name=='nt' else 'clear')
    print(f"{datetime.now()} 即時股價更新:")
    print(f"{'股票':<8} {'即時價':>10}")
    print("-"*30)
    for data in stock_data_list:
        print(f"{data['股票']:<8} {data['即時價']:>10}")

    print("\n📢 最新新聞摘要:")
    for stock_id, news in news_summary_dict.items():
        if news:
            title = news.get("標題","")
            snippet = news.get("摘要","")
            print(f"{stock_id}: {title} | {snippet}")
        else:
            print(f"{stock_id}: 無最新新聞")

# =========================
# 主程式
if __name__ == "__main__":
    ensure_csv_file()
    ensure_news_csv()
    try:
        while True:
            all_data = []
            latest_news_summary = {}
            for s in stocks:
                # 即時股價顯示
                price = get_realtime_price(s)
                all_data.append({"股票": s, "即時價": price})
                # 收盤價每天固定抓
                close_price = get_daily_close(s)
                save_close_price(s, close_price)
                # 新聞抓取
                news = fetch_news(s)
                save_news(news)
                latest_news_summary[s] = news[0] if news else None

            display_realtime(all_data, latest_news_summary)
            print(f"\n下一次更新: {stock_interval} 秒後")
            time.sleep(stock_interval)
    except KeyboardInterrupt:
        print("\n程式已手動停止，退出中...")