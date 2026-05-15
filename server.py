"""닝겐주식 로컬 서버 - python server.py"""
import http.server, json, urllib.request, urllib.parse, ssl, os, time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

PORT = 5502
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"
NAVER_STOCK = "https://polling.finance.naver.com/api/realtime/domestic/stock"
NAVER_INDEX = "https://polling.finance.naver.com/api/realtime/domestic/index"
NAVER_CHART = "https://fchart.stock.naver.com/sise.nhn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
POOL = ThreadPoolExecutor(max_workers=30)
CACHE = {}
CACHE_TTL = 15

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "index.html"), "rb") as f:
    INDEX_HTML = f.read()
KIS_HTML = b""
kis_path = os.path.join(ROOT, "kis.html")
if os.path.exists(kis_path):
    with open(kis_path, "rb") as f:
        KIS_HTML = f.read()

KIS_REAL = "https://openapi.koreainvestment.com:9443"
KIS_MOCK = "https://openapivts.koreainvestment.com:29443"


def parse_num(s):
    """'1,234,567' or '878727천주' -> number"""
    if s is None:
        return 0
    if isinstance(s, (int, float)):
        return s
    import re
    cleaned = re.sub(r'[^\d.\-+]', '', str(s))
    try:
        return float(cleaned) if cleaned else 0
    except ValueError:
        return 0


# ===== 네이버 API =====
def fetch_naver_stocks(codes):
    """네이버 Polling API로 한국 주식 여러개 한번에 조회"""
    cached_key = "naver_" + ",".join(codes)
    cached = CACHE.get(cached_key)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    try:
        url = f"{NAVER_STOCK}/{','.join(codes)}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())
        results = {}
        for r in data.get("datas", []):
            code = r.get("itemCode", "")
            results[code] = {
                "price": parse_num(r.get("closePrice")),
                "prevClose": parse_num(r.get("closePrice")) - parse_num(r.get("compareToPreviousClosePrice")),
                "open": parse_num(r.get("openPrice")),
                "high": parse_num(r.get("highPrice")),
                "low": parse_num(r.get("lowPrice")),
                "volume": parse_num(r.get("accumulatedTradingVolume")),
                "change": parse_num(r.get("compareToPreviousClosePrice")),
                "changeRate": parse_num(r.get("fluctuationsRatio")),
            }
        CACHE[cached_key] = (time.time(), results)
        return results
    except Exception as e:
        return {}


def fetch_naver_index(index_code):
    """네이버 Polling API로 지수 조회 (KOSPI, KOSDAQ)"""
    cached = CACHE.get("idx_" + index_code)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    try:
        url = f"{NAVER_INDEX}/{index_code}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())
        r = data.get("datas", [{}])[0]
        result = {
            "price": parse_num(r.get("closePrice")),
            "change": parse_num(r.get("compareToPreviousClosePrice")),
            "changeRate": parse_num(r.get("fluctuationsRatio")),
            "open": parse_num(r.get("openPrice")),
            "high": parse_num(r.get("highPrice")),
            "low": parse_num(r.get("lowPrice")),
            "volume": parse_num(r.get("accumulatedTradingVolume")),
            "prevClose": parse_num(r.get("closePrice")) - parse_num(r.get("compareToPreviousClosePrice")),
        }
        CACHE["idx_" + index_code] = (time.time(), result)
        return result
    except Exception as e:
        print(f"  [ERROR] fetch_naver_index({index_code}): {e}")
        import traceback; traceback.print_exc()
        return None


def fetch_naver_chart(code):
    """네이버 차트 API (일봉 30일)"""
    try:
        url = f"{NAVER_CHART}?symbol={code}&timeframe=day&count=30&requestType=0"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            raw = resp.read().decode("euc-kr", errors="ignore")
        closes, volumes = [], []
        for m in __import__("re").findall(r'data="([^"]+)"', raw):
            parts = m.split("|")
            if len(parts) >= 6:
                closes.append(float(parts[4]))
                volumes.append(float(parts[5]))
        return {"closes": closes, "volumes": volumes}
    except Exception:
        return {"closes": [], "volumes": []}


# ===== Yahoo Finance (해외 전용) =====
def fetch_yahoo_one(sym):
    cached = CACHE.get("y_" + sym)
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
            prev = m.get("chartPreviousClose") or m.get("previousClose") or 0
            price = m.get("regularMarketPrice") or 0
            chg = m.get("regularMarketChange") or round(price - prev, 2)
            chg_pct = m.get("regularMarketChangePercent") or (round((price - prev) / prev * 100, 2) if prev else 0)
            result = {
                "price": price, "prevClose": prev,
                "open": m.get("regularMarketDayOpen") or 0,
                "high": m.get("regularMarketDayHigh") or 0,
                "low": m.get("regularMarketDayLow") or 0,
                "volume": m.get("regularMarketVolume") or 0,
                "change": round(chg, 2), "changeRate": round(chg_pct, 2),
            }
            CACHE["y_" + sym] = (time.time(), result)
            return sym, result
    except Exception as e:
        return sym, {"error": str(e)}
    return sym, {"error": "no data"}


def fetch_yahoo_chart(sym, rng="1mo"):
    try:
        url = f"{YAHOO}/{urllib.parse.quote(sym)}?interval=1d&range={rng}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            data = json.loads(resp.read())
        r = data.get("chart", {}).get("result", [None])[0]
        if r:
            q = r.get("indicators", {}).get("quote", [{}])[0]
            return sym, {"closes": [v for v in (q.get("close") or []) if v], "volumes": [v for v in (q.get("volume") or []) if v]}
    except Exception:
        pass
    return sym, {"closes": [], "volumes": []}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            p = self.path
            if p == "/" or p == "/index.html":
                self.serve_html(INDEX_HTML)
            elif p == "/kis.html" or p == "/kis":
                self.serve_html(KIS_HTML)
            elif p.startswith("/api/kis/"):
                self.handle_kis_proxy()
            elif p.startswith("/api/naver"):
                self.handle_naver()
            elif p.startswith("/api/price"):
                self.handle_yahoo_price()
            elif p.startswith("/api/charts"):
                self.handle_yahoo_charts()
            elif p.startswith("/api/news"):
                self.handle_news()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception:
            import traceback; traceback.print_exc()

    def serve_html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def handle_kis_proxy(self):
        """KIS API 프록시 - /api/kis/real/... or /api/kis/mock/..."""
        try:
            path = self.path[len("/api/kis/"):]
            if path.startswith("real/"):
                base = KIS_REAL
                api_path = path[4:]
            elif path.startswith("mock/"):
                base = KIS_MOCK
                api_path = path[4:]
            else:
                self.send_json({"error": "use /api/kis/real/ or /api/kis/mock/"})
                return
            url = base + api_path
            headers = {}
            for key in ['content-type','authorization','appkey','appsecret','tr_id','custtype']:
                val = self.headers.get(key)
                if val: headers[key] = val
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_json({"error": str(e)})

    def do_POST(self):
        """KIS 토큰 발급용 POST 프록시"""
        try:
            if self.path.startswith("/api/kis/"):
                path = self.path[len("/api/kis/"):]
                if path.startswith("real/"):
                    base = KIS_REAL
                    api_path = path[4:]
                elif path.startswith("mock/"):
                    base = KIS_MOCK
                    api_path = path[4:]
                else:
                    self.send_json({"error": "invalid"}); return
                url = base + api_path
                length = int(self.headers.get('content-length', 0))
                body = self.rfile.read(length) if length else None
                headers = {"Content-Type": "application/json"}
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()
        except Exception as e:
            self.send_json({"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, authorization, appkey, appsecret, tr_id, custtype")
        self.end_headers()

    def handle_naver(self):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            typ = params.get("type", [""])[0]
            codes = [s.strip() for s in params.get("codes", [""])[0].split(",") if s.strip()]
            if typ == "stocks":
                self.send_json(fetch_naver_stocks(codes))
            elif typ == "index":
                results = {}
                for code in codes:
                    r = fetch_naver_index(code)
                    if r: results[code] = r
                self.send_json(results)
            elif typ == "charts":
                results = {}
                futures = {POOL.submit(fetch_naver_chart, c): c for c in codes}
                for f in as_completed(futures):
                    c = futures[f]
                    results[c] = f.result()
                self.send_json(results)
            else:
                self.send_json({"error": "invalid type"})
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json({"error": str(e)})

    def handle_yahoo_price(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        symbols = [s.strip() for s in params.get("symbols", [""])[0].split(",") if s.strip()]
        results = {}
        futures = {POOL.submit(fetch_yahoo_one, sym): sym for sym in symbols}
        for f in as_completed(futures):
            sym, data = f.result()
            results[sym] = data
        self.send_json(results)

    def handle_yahoo_charts(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        symbols = [s.strip() for s in params.get("symbols", [""])[0].split(",") if s.strip()]
        results = {}
        futures = {POOL.submit(fetch_yahoo_chart, sym): sym for sym in symbols}
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
http.server.ThreadingHTTPServer(("", PORT), Handler).serve_forever()
