# ============
#建立SQL連線(Azure SQL Database)
import pyodbc
print(pyodbc.drivers())

server = 'linpeichunhappy.database.windows.net'  # Azure SQL Server 名稱
database = 'stock_project'                   # 資料庫名稱
username = 'missa'                       # 帳號
password = 'Cc12345678'                   # 密碼
driver = '{ODBC Driver 18 for SQL Server}'   # 建議用最新 ODBC Driver

# 建立連線
conn = pyodbc.connect(f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;')
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

print("✅ 連線成功")