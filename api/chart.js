export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const { symbol, range = '1mo' } = req.query;
  if (!symbol) return res.status(400).json({ error: 'symbol required' });

  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=${range}`;
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
    });
    const data = await resp.json();
    const r = data.chart?.result?.[0];
    if (!r) return res.json({ closes: [], volumes: [] });

    const q = r.indicators?.quote?.[0] || {};
    const closes = (q.close || []).filter(v => v != null);
    const volumes = (q.volume || []).filter(v => v != null);
    res.json({ closes, volumes });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
