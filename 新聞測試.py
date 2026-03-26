import feedparser
import urllib.parse

# =========================
# 原本股票清單（完整保留）
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
# 抓新聞（修正版）
def fetch_news(stock_id):
    company = company_names.get(stock_id, "")
    if not company:
        return []

    # 🔥 關鍵字（你可以之後再優化）
    keyword = f"{stock_id} OR {company} stock"

    # ✅ 解決你剛剛的錯誤（URL 編碼）
    encoded_keyword = urllib.parse.quote(keyword)

    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(url)

        news_list = []
        for entry in feed.entries[:5]:
            news = {
                "標題": entry.title,
                "連結": entry.link,
                "來源": entry.source.title if hasattr(entry, "source") else "",
                "摘要": entry.summary if hasattr(entry, "summary") else ""
            }
            news_list.append(news)

        return news_list

    except Exception as e:
        print(f"❌ {stock_id} 抓取錯誤: {e}")
        return []

# =========================
# 測試主程式
if __name__ == "__main__":
    for s in stocks:
        print(f"\n====== {s} 新聞 ======")

        news_list = fetch_news(s)

        if not news_list:
            print("⚠️ 沒抓到新聞")
        else:
            for i, news in enumerate(news_list, 1):
                print(f"\n[{i}] {news['標題']}")
                print(f"來源: {news['來源']}")
                print(f"連結: {news['連結']}")
                print(f"摘要: {news['摘要'][:100]}...")