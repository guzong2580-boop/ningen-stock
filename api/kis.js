const KIS_REAL = 'https://openapi.koreainvestment.com:9443';
const KIS_MOCK = 'https://openapivts.koreainvestment.com:29443';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, authorization, appkey, appsecret, tr_id, custtype');
  if (req.method === 'OPTIONS') return res.status(204).end();

  // path: /api/kis?env=real&path=/oauth2/tokenP
  const { env, path } = req.query;
  if (!env || !path) return res.status(400).json({ error: 'env and path required' });

  const base = env === 'mock' ? KIS_MOCK : KIS_REAL;
  const url = base + path;

  const headers = {};
  for (const key of ['content-type', 'authorization', 'appkey', 'appsecret', 'tr_id', 'custtype']) {
    if (req.headers[key]) headers[key] = req.headers[key];
  }

  try {
    const opts = { method: req.method, headers };
    if (req.method === 'POST' && req.body) {
      opts.body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
      headers['Content-Type'] = 'application/json';
    }
    const r = await fetch(url, opts);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(502).json({ error: e.message });
  }
}
