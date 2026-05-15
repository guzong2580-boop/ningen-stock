export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const feeds = [
    'https://news.google.com/rss/search?q=%EC%A3%BC%EC%8B%9D+%EC%A6%9D%EC%8B%9C&hl=ko&gl=KR&ceid=KR:ko',
    'https://news.google.com/rss/search?q=%ED%99%98%EC%9C%A8+%EA%B2%BD%EC%A0%9C&hl=ko&gl=KR&ceid=KR:ko',
  ];
  const articles = [];
  for (const url of feeds) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
      const xml = await r.text();
      const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)];
      for (const m of items.slice(0, 15)) {
        const t = m[1].match(/<title>(.*?)<\/title>/)?.[1] || '';
        const l = m[1].match(/<link>(.*?)<\/link>/)?.[1] || '';
        const p = m[1].match(/<pubDate>(.*?)<\/pubDate>/)?.[1] || '';
        const s = m[1].match(/<source.*?>(.*?)<\/source>/)?.[1] || '';
        articles.push({ title: t.replace(/<!\[CDATA\[|\]\]>/g, ''), link: l, pub: p, source: s });
      }
    } catch (e) {}
  }
  const seen = new Set();
  const unique = articles.filter(a => { if (seen.has(a.title)) return false; seen.add(a.title); return true; });
  res.json(unique.slice(0, 30));
}
