"""닝겐주식 로컬 서버 - python server.py"""
import http.server, json, urllib.request, urllib.parse, ssl, os, time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

PORT = 5502
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
POOL = ThreadPoolExecutor(max_workers=30)
CACHE = {}       # sym -> (timestamp, data)
CACHE_TTL = 20   # 20초 캐시

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "index.html"), "rb") as f:
    INDEX_HTML = f.read()


def fetch_one(sym):
    """Yahoo Finance에서 종목 1개 가져오기 (캐시 확인)"""
    cached = CACHE.get(sym)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return sym, cached[1]
    try:
        url = f"{YAHOO}/{urllib.parse.quote(sym)}?interval=1d&range=5d"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())
        r = data.get("chart", {}).get("result", [None])[0]
        if r:
            m = r["meta"]
            q = r.get("indicators", {}).get("quote", [{}])[0]
            prev = m.get("chartPreviousClose") or m.get("previousClose") or 0
            price = m.get("regularMarketPrice") or 0
            chg = m.get("regularMarketChange")
            chg_pct = m.get("regularMarketChangePercent")
            if chg is None:
                chg = round(price - prev, 2)
            if chg_pct is None:
                chg_pct = round((price - prev) / prev * 100, 2) if prev else 0
            result = {
                "price": price, "prevClose": prev,
                "open": (q.get("open") or [0])[-1] if q.get("open") else 0,
                "high": m.get("regularMarketDayHigh") or 0,
                "low": m.get("regularMarketDayLow") or 0,
                "volume": m.get("regularMarketVolume") or 0,
                "change": round(chg, 2),
                "changeRate": round(chg_pct, 2),
            }
            CACHE[sym] = (time.time(), result)
            return sym, result
    except Exception as e:
        return sym, {"error": str(e)}
    return sym, {"error": "no data"}


def fetch_chart_one(sym, rng="1mo"):
    """Yahoo Finance에서 차트 1개 가져오기"""
    try:
        url = f"{YAHOO}/{urllib.parse.quote(sym)}?interval=1d&range={rng}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())
        r = data.get("chart", {}).get("result", [None])[0]
        if r:
            q = r.get("indicators", {}).get("quote", [{}])[0]
            closes = [v for v in (q.get("close") or []) if v is not None]
            volumes = [v for v in (q.get("volume") or []) if v is not None]
            return sym, {"closes": closes, "volumes": volumes}
    except Exception:
        pass
    return sym, {"closes": [], "volumes": []}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(INDEX_HTML))
                self.end_headers()
                self.wfile.write(INDEX_HTML)
            elif self.path.startswith("/api/price"):
                self.handle_price()
            elif self.path.startswith("/api/charts"):
                self.handle_charts()
            elif self.path.startswith("/api/chart"):
                self.handle_chart()
            elif self.path.startswith("/api/news"):
                self.handle_news()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception:
            import traceback; traceback.print_exc()

    def handle_price(self):
        """병렬로 여러 종목 가격 조회"""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        symbols = [s.strip() for s in params.get("symbols", [""])[0].split(",") if s.strip()]
        results = {}
        futures = {POOL.submit(fetch_one, sym): sym for sym in symbols}
        for f in as_completed(futures):
            sym, data = f.result()
            results[sym] = data
        self.send_json(results)

    def handle_chart(self):
        """단일 차트"""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        symbol = params.get("symbol", [""])[0]
        rng = params.get("range", ["1mo"])[0]
        _, data = fetch_chart_one(symbol, rng)
        self.send_json(data)

    def handle_charts(self):
        """병렬로 여러 차트 조회"""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        symbols = [s.strip() for s in params.get("symbols", [""])[0].split(",") if s.strip()]
        rng = params.get("range", ["1mo"])[0]
        results = {}
        futures = {POOL.submit(fetch_chart_one, sym, rng): sym for sym in symbols}
        for f in as_completed(futures):
            sym, data = f.result()
            results[sym] = data
        self.send_json(results)

    def handle_news(self):
        try:
            feeds = [
                "https://news.google.com/rss/search?q=%EC%A3%BC%EC%8B%9D+%EC%A6%9D%EC%8B%9C+when%3A1d&hl=ko&gl=KR&ceid=KR:ko",
                "https://news.google.com/rss/search?q=%ED%99%98%EC%9C%A8+%EA%B2%BD%EC%A0%9C+when%3A1d&hl=ko&gl=KR&ceid=KR:ko",
                "https://news.google.com/rss/search?q=%EC%9B%90%EC%9E%90%EC%9E%AC+%EC%9C%A0%EA%B0%80+%EA%B8%88+when%3A1d&hl=ko&gl=KR&ceid=KR:ko",
            ]
            articles = []
            for feed_url in feeds:
                try:
                    req = urllib.request.Request(feed_url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as resp:
                        raw = resp.read()
                    root = ET.fromstring(raw)
                    for item in root.findall(".//item")[:15]:
                        articles.append({
                            "title": item.findtext("title", ""),
                            "link": item.findtext("link", ""),
                            "pub": item.findtext("pubDate", ""),
                            "source": item.findtext("source", ""),
                        })
                except Exception:
                    pass
            seen = set()
            unique = [a for a in articles if a["title"] not in seen and not seen.add(a["title"])]
            unique.sort(key=lambda a: a.get("pub", ""), reverse=True)
            self.send_json(unique[:30])
        except Exception as e:
            self.send_json({"error": str(e)})

    def send_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        try:
            msg = fmt % args if args else fmt
            if "/api/" in msg:
                print(f"  {msg}")
        except Exception:
            pass


print(f"\n  닝겐주식 대시보드")
print(f"  http://localhost:{PORT}")
print(f"  종료: Ctrl+C\n")

server = http.server.ThreadingHTTPServer(("", PORT), Handler)
server.serve_forever()
