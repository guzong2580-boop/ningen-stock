const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36';

function parseNum(s) {
  if (s == null) return 0;
  if (typeof s === 'number') return s;
  return parseFloat(String(s).replace(/,/g, '').replace('+', '')) || 0;
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const { type, codes } = req.query;
  if (!type || !codes) return res.status(400).json({ error: 'type and codes required' });

  const codeList = codes.split(',').filter(Boolean);

  if (type === 'stocks') {
    try {
      const url = `https://polling.finance.naver.com/api/realtime/domestic/stock/${codeList.join(',')}`;
      const r = await fetch(url, { headers: { 'User-Agent': UA } });
      const data = await r.json();
      const results = {};
      for (const d of (data.datas || [])) {
        results[d.itemCode] = {
          price: parseNum(d.closePrice),
          prevClose: parseNum(d.closePrice) - parseNum(d.compareToPreviousClosePrice),
          open: parseNum(d.openPrice),
          high: parseNum(d.highPrice),
          low: parseNum(d.lowPrice),
          volume: parseNum(d.accumulatedTradingVolume),
          change: parseNum(d.compareToPreviousClosePrice),
          changeRate: parseNum(d.fluctuationsRatio),
        };
      }
      return res.json(results);
    } catch (e) { return res.json({}); }
  }

  if (type === 'index') {
    const results = {};
    for (const code of codeList) {
      try {
        const url = `https://polling.finance.naver.com/api/realtime/domestic/index/${code}`;
        const r = await fetch(url, { headers: { 'User-Agent': UA } });
        const data = await r.json();
        const d = (data.datas || [])[0];
        if (d) {
          results[code] = {
            price: parseNum(d.closePrice),
            change: parseNum(d.compareToPreviousClosePrice),
            changeRate: parseNum(d.fluctuationsRatio),
            open: parseNum(d.openPrice),
            high: parseNum(d.highPrice),
            low: parseNum(d.lowPrice),
            volume: parseNum(d.accumulatedTradingVolume),
            prevClose: parseNum(d.closePrice) - parseNum(d.compareToPreviousClosePrice),
          };
        }
      } catch (e) {}
    }
    return res.json(results);
  }

  if (type === 'charts') {
    const results = {};
    await Promise.all(codeList.map(async (code) => {
      try {
        const url = `https://fchart.stock.naver.com/sise.nhn?symbol=${code}&timeframe=day&count=30&requestType=0`;
        const r = await fetch(url, { headers: { 'User-Agent': UA } });
        const text = await r.text();
        const closes = [], volumes = [];
        for (const m of text.matchAll(/data="([^"]+)"/g)) {
          const p = m[1].split('|');
          if (p.length >= 6) { closes.push(+p[4]); volumes.push(+p[5]); }
        }
        results[code] = { closes, volumes };
      } catch (e) { results[code] = { closes: [], volumes: [] }; }
    }));
    return res.json(results);
  }

  res.status(400).json({ error: 'invalid type' });
}
