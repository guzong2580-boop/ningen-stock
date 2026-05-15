export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const symbols = (req.query.symbols || '').split(',').filter(Boolean);
  const range = req.query.range || '1mo';
  if (!symbols.length) return res.status(400).json({ error: 'symbols required' });

  const results = {};
  await Promise.all(symbols.map(async (sym) => {
    try {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1d&range=${range}`;
      const resp = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
      });
      const data = await resp.json();
      const r = data.chart?.result?.[0];
      if (r) {
        const q = r.indicators?.quote?.[0] || {};
        results[sym] = {
          closes: (q.close || []).filter(v => v != null),
          volumes: (q.volume || []).filter(v => v != null),
        };
      } else {
        results[sym] = { closes: [], volumes: [] };
      }
    } catch (e) {
      results[sym] = { closes: [], volumes: [] };
    }
  }));
  res.json(results);
}
