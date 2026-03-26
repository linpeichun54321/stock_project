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

# 更新間隔（秒）
update_interval = 10 * 60  # 10 分鐘

# 美國東部時區
eastern = pytz.timezone("US/Eastern")

# =========================
# CSV 相關函數
def get_csv_filename():
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"stock_realtime_{date_str}.csv"  # 新 CSV 名稱，區分每日收盤 CSV

def ensure_csv_file():
    csv_file = get_csv_filename()
    if not os.path.exists(csv_file):
        with open(csv_file, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["日期", "股票", "即時價", "開盤", "最高", "最低", "收盤", "成交量"])
    return csv_file

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
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='stock_realtime' AND xtype='U')
CREATE TABLE stock_realtime (
    record_time DATETIME,
    stock_id NVARCHAR(10),
    price FLOAT,
    open_price FLOAT,
    high FLOAT,
    low FLOAT,
    close_price FLOAT,
    volume BIGINT,
    PRIMARY KEY(record_time, stock_id)
)
""")
conn.commit()
print("✅ SQL 連線成功")

# =========================
# 抓股票資料
def get_stock_data(stock_id):
    stock = yf.Ticker(stock_id)
    try:
        df_day = stock.history(period="1d")
        if df_day.empty:
            open_price = high = low = close_price = volume = None
        else:
            last_day = df_day.iloc[-1]
            open_price = last_day["Open"]
            high = last_day["High"]
            low = last_day["Low"]
            close_price = last_day["Close"]
            volume = last_day["Volume"]

        df_min = stock.history(period="1d", interval="1m")
        if df_min.empty:
            price = None
        else:
            price = df_min["Close"].iloc[-1]

        return {
            "股票": stock_id,
            "即時價": price,
            "開盤": open_price,
            "最高": high,
            "最低": low,
            "收盤": close_price,
            "成交量": volume
        }
    except Exception as e:
        print(f"❌ {stock_id} 抓取失敗: {e}")
        return {
            "股票": stock_id,
            "即時價": None,
            "開盤": None,
            "最高": None,
            "最低": None,
            "收盤": None,
            "成交量": None
        }

# =========================
# 寫入 SQL
def save_to_sql(data):
    now_time = datetime.now(eastern)
    try:
        cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM stock_realtime
            WHERE record_time = ? AND stock_id = ?
        )
        INSERT INTO stock_realtime
        (record_time, stock_id, price, open_price, high, low, close_price, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, now_time, data["股票"],
             now_time, data["股票"], data["即時價"], data["開盤"],
             data["最高"], data["最低"], data["收盤"], data["成交量"])
        conn.commit()
    except Exception as e:
        print(f"❌ SQL 寫入失敗 {data['股票']}: {e}")

# =========================
# 寫入 CSV
def save_to_csv(data):
    csv_file = ensure_csv_file()
    now_time = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S")
    with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            now_time, data["股票"], data["即時價"], data["開盤"],
            data["最高"], data["最低"], data["收盤"], data["成交量"]
        ])

# =========================
# 顯示即時
def display_realtime(stock_data_list):
    print(f"{datetime.now()} 即時股價更新:")
    print(f"{'股票':<8} {'即時價':>10} {'開盤':>10} {'最高':>10} {'最低':>10} {'收盤':>10} {'成交量':>15}")
    print("-"*90)
    for d in stock_data_list:
        print(f"{d['股票']:<8} {d['即時價']!s:>10} {d['開盤']!s:>10} {d['最高']!s:>10} {d['最低']!s:>10} {d['收盤']!s:>10} {d['成交量']!s:>15}")

# =========================
# 主程式
if __name__ == "__main__":
    ensure_csv_file()
    while True:
        all_data = []
        for s in stocks:
            data = get_stock_data(s)
            all_data.append(data)
            save_to_csv(data)
            save_to_sql(data)
        display_realtime(all_data)
        print(f"\n下一次更新: {update_interval//60} 分鐘後\n")
        time.sleep(update_interval)