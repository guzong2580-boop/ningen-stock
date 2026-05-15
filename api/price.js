export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const symbols = (req.query.symbols || '').split(',').filter(Boolean);
  if (!symbols.length) return res.status(400).json({ error: 'symbols required' });

  const results = {};
  await Promise.all(symbols.map(async (sym) => {
    try {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1d&range=5d`;
      const resp = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
      });
      const data = await resp.json();
      const r = data.chart?.result?.[0];
      if (r) {
        const m = r.meta;
        const prev = m.chartPreviousClose || m.previousClose || 0;
        const price = m.regularMarketPrice || 0;
        const q = r.indicators?.quote?.[0] || {};
        const len = q.close?.length || 0;
        results[sym] = {
          price,
          prevClose: prev,
          open: q.open?.[len - 1] || m.regularMarketDayOpen || 0,
          high: m.regularMarketDayHigh || (len ? Math.max(...q.high.filter(Boolean)) : 0),
          low: m.regularMarketDayLow || (len ? Math.min(...q.low.filter(Boolean)) : 0),
          volume: m.regularMarketVolume || 0,
          change: +(price - prev).toFixed(2),
          changeRate: prev ? +((price - prev) / prev * 100).toFixed(2) : 0,
        };
      }
    } catch (e) {
      results[sym] = { error: e.message };
    }
  }));
  res.json(results);
}
