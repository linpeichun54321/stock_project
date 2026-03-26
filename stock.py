import yfinance as yf
import time
from datetime import datetime
import csv
import os
import pytz  # 時區判斷
import pyodbc

# =========================
# 股票清單
stocks = [
    "AAPL", "MSFT", "GOOGL", "NVDA",
    "XOM", "CVX", "JPM", "GS",
    "LMT", "BA", "TSLA", "^DJI"
]
# =========================

# 即時更新間隔（秒）
stock_interval = 30

# 記錄今天已存入收盤價的股票，避免重複寫入
saved_today = set()
today_date = datetime.now().strftime("%Y-%m-%d")

# 美國東部時區
eastern = pytz.timezone("US/Eastern")

# =========================
# CSV 相關函數
def get_csv_filename():
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"stock_close_{date_str}.csv"

def ensure_csv_file():
    csv_file = get_csv_filename()
    if not os.path.exists(csv_file):
        with open(csv_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["日期", "股票", "收盤價"])
    return csv_file

# =========================
# 股票資料抓取
def get_stock_data(stock_id):
    stock = yf.Ticker(stock_id)
    try:
        # 日線資料
        df_day = stock.history(period="1d")
        if df_day.empty:
            open_price = high = low = close = volume = "無資料"
        else:
            last_day = df_day.iloc[-1]
            open_price = last_day["Open"]
            high = last_day["High"]
            low = last_day["Low"]
            close = last_day["Close"]
            volume = last_day["Volume"]

        # 1 分鐘即時價
        df_min = stock.history(period="1d", interval="1m")
        if df_min.empty:
            price = "無資料"
        else:
            price = df_min["Close"].iloc[-1]

        return {
            "股票": stock_id,
            "即時價": price,
            "開盤": open_price,
            "最高": high,
            "最低": low,
            "收盤": close,
            "成交量": volume
        }
    except Exception:
        return {
            "股票": stock_id,
            "即時價": "錯誤",
            "開盤": "-",
            "最高": "-",
            "最低": "-",
            "收盤": "-",
            "成交量": "-"
        }

# =========================
# 判斷美股收盤
def is_us_market_closed():
    now = datetime.now(eastern)
    return now.hour >= 16  # 東部時間 16:00 之後

# =========================
# SQL Server 連線設定
server = 'linpeichunhappy.database.windows.net'
database = 'stock_project'
username = 'missa'
password = 'Cc12345678'  # ⚠️ 建議改成環境變數
driver = '{ODBC Driver 18 for SQL Server}'

conn = pyodbc.connect(
    f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
)
cursor = conn.cursor()

# 建表（如果不存在）
cursor.execute("""
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='stock_close' AND xtype='U')
CREATE TABLE stock_close (
    date DATE,
    stock_id NVARCHAR(10),
    close_price FLOAT,
    PRIMARY KEY(date, stock_id)
)
""")
conn.commit()
print("✅ SQL 連線成功")

# =========================
# 寫入收盤價 (CSV + SQL)
def save_close_price(stock_id, close_price):
    """只在收盤時間存檔，每天一次（CSV + SQL）"""
    global saved_today, today_date
    now_date = datetime.now().strftime("%Y-%m-%d")
    csv_file = ensure_csv_file()

    # 換天，重置 saved_today
    if now_date != today_date:
        saved_today = set()
        today_date = now_date
        csv_file = ensure_csv_file()

    if stock_id in saved_today:
        return  # 已存過，不重複存

    if close_price in ["-", "無資料"]:
        return

    if is_us_market_closed():
        # ====== CSV 寫入 (保留原本內容) ======
        with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([now_date, stock_id, close_price])

        # ====== SQL 寫入 ======
        try:
            cursor.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM stock_close 
                WHERE date = ? AND stock_id = ?
            )
            INSERT INTO stock_close (date, stock_id, close_price)
            VALUES (?, ?, ?)
            """, now_date, stock_id, now_date, stock_id, float(close_price))
            conn.commit()
        except Exception as e:
            print(f"❌ SQL寫入失敗: {stock_id}, {e}")

        saved_today.add(stock_id)

# =========================
# 顯示即時股價
def display_realtime(stock_data_list):
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{datetime.now()} 即時股價更新:")
    print(f"{'股票':<8} {'即時價':>10} {'開盤':>10} {'最高':>10} {'最低':>10} {'收盤':>10} {'成交量':>15}")
    print("-"*80)
    for data in stock_data_list:
        print(f"{data['股票']:<8} {data['即時價']:>10} {data['開盤']:>10} {data['最高']:>10} {data['最低']:>10} {data['收盤']:>10} {data['成交量']:>15}")

# =========================
# 主程式
if __name__ == "__main__":
    ensure_csv_file()
    while True:
        all_data = []
        for s in stocks:
            data = get_stock_data(s)
            all_data.append(data)
            save_close_price(s, data["收盤"])
        display_realtime(all_data)
        print(f"\n下一次更新: {stock_interval} 秒後")
        time.sleep(stock_interval)
