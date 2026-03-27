import yfinance as yf
import time
from datetime import datetime
import csv
import os
import pytz
import pyodbc

# =========================
# 股票清單
stocks = [
    "AAPL", "MSFT", "GOOGL", "NVDA",
    "XOM", "CVX", "JPM", "GS",
    "LMT", "BA", "TSLA", "^DJI"
]

stock_interval = 30
saved_today = set()
today_date = datetime.now().strftime("%Y-%m-%d")
eastern = pytz.timezone("US/Eastern")

# =========================
# CSV 檔案名稱
HIST_CSV_FILE = "stock_close_last_month.csv"

def ensure_history_csv():
    if not os.path.exists(HIST_CSV_FILE):
        with open(HIST_CSV_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["日期", "股票", "收盤價"])

def save_history_csv(stock_id, date_str, close_price):
    with open(HIST_CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([date_str, stock_id, close_price])

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

print("✅ SQL 連線成功")

# =========================
# 自動檢查並建立 dbo.stock_close
def ensure_sql_table():
    cursor.execute("""
    IF NOT EXISTS (
        SELECT * FROM sysobjects WHERE name='stock_close' AND xtype='U'
    )
    CREATE TABLE dbo.stock_close (
        date DATE,
        stock_id NVARCHAR(10),
        close_price FLOAT,
        PRIMARY KEY(date, stock_id)
    )
    """)
    conn.commit()
    print("✅ SQL 表格 dbo.stock_close 已確認或建立完成")

ensure_sql_table()  # 啟動時先確認

# =========================
def is_us_market_closed():
    now = datetime.now(eastern)
    return now.hour >= 16

# =========================
def get_stock_data(stock_id):
    stock = yf.Ticker(stock_id)
    try:
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

        df_min = stock.history(period="1d", interval="1m")
        price = df_min["Close"].iloc[-1] if not df_min.empty else "無資料"

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
def save_close_price(stock_id, close_price, date_str=None):
    global saved_today, today_date
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    csv_file = f"stock_close_{date_str}.csv"

    if date_str != today_date:
        saved_today = set()
        today_date = date_str

    if (date_str, stock_id) in saved_today:
        return

    if close_price in ["-", "無資料"]:
        return

    # CSV 寫入
    with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([date_str, stock_id, close_price])

    # SQL 寫入
    try:
        cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM dbo.stock_close WHERE date = ? AND stock_id = ?
        )
        INSERT INTO dbo.stock_close (date, stock_id, close_price) VALUES (?, ?, ?)
        """, date_str, stock_id, date_str, stock_id, float(close_price))
        conn.commit()
    except Exception as e:
        print(f"❌ SQL寫入失敗: {stock_id} {date_str}, {e}")

    saved_today.add((date_str, stock_id))

# =========================
def display_realtime(stock_data_list):
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{datetime.now()} 即時股價更新:")
    print(f"{'股票':<8} {'即時價':>10} {'開盤':>10} {'最高':>10} {'最低':>10} {'收盤':>10} {'成交量':>15}")
    print("-"*80)
    for data in stock_data_list:
        print(f"{data['股票']:<8} {data['即時價']:>10} {data['開盤']:>10} {data['最高']:>10} {data['最低']:>10} {data['收盤']:>10} {data['成交量']:>15}")

# =========================
def fetch_last_month_history():
    print("⏳ 抓取過去一個月歷史收盤價到單一檔案並寫入 SQL...")
    ensure_history_csv()
    for s in stocks:
        stock = yf.Ticker(s)
        df = stock.history(period="1mo")
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            close_price = row["Close"]

            # CSV
            save_history_csv(s, date_str, close_price)

            # SQL
            try:
                cursor.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.stock_close WHERE date = ? AND stock_id = ?
                )
                INSERT INTO dbo.stock_close (date, stock_id, close_price) VALUES (?, ?, ?)
                """, date_str, s, date_str, s, float(close_price))
                conn.commit()
            except Exception as e:
                print(f"❌ SQL寫入失敗: {s} {date_str}, {e}")
    print(f"✅ 過去一個月歷史收盤價已寫入 {HIST_CSV_FILE} + SQL")

# =========================
if __name__ == "__main__":
    ensure_history_csv()
    fetch_last_month_history()
    while True:
        all_data = []
        for s in stocks:
            data = get_stock_data(s)
            all_data.append(data)
            if is_us_market_closed():
                save_close_price(s, data["收盤"])
        display_realtime(all_data)
        print(f"\n下一次更新: {stock_interval} 秒後")
        time.sleep(stock_interval)