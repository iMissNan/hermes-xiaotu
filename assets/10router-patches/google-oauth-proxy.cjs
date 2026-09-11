// [LOCAL PATCH 2026-09-09 rev2] Google OAuth token 刷新专用代理钩子
// 背景: 10Router 后台 token 刷新用裸 fetch 调 https://oauth2.googleapis.com/token，
//       CN 直连被墙 → antigravity 每小时掉线 (401)。
// 做法: NODE_OPTIONS=--require 预加载，仅拦截 oauth2.googleapis.com 的 fetch，
//       经 HTTP CONNECT 隧道 (GOOGLE_TOKEN_PROXY, 默认 172.17.0.1:7892) + TLS 转发。
//       其余流量原样放行。代理失败自动退回原生 fetch。
'use strict';
const net = require('net');
const tls = require('tls');
const http = require('http');

const PROXY_LIST = (process.env.GOOGLE_TOKEN_PROXY || 'http://172.17.0.1:7892,http://172.17.0.1:7894').split(',').map(s => s.trim()).filter(Boolean);
const TARGET_HOSTS = new Set(['oauth2.googleapis.com']);
const origFetch = globalThis.fetch;

function openTunnel(host, port, timeoutMs, PROXY_URL) {
  return new Promise((resolve, reject) => {
    const p = new URL(PROXY_URL);
    const sock = net.connect({ host: p.hostname, port: Number(p.port || 80) });
    let acc = '';
    let settled = false;
    const fail = (msg, err) => { if (!settled) { settled = true; sock.destroy(); reject(err || new Error(msg)); } };
    const to = setTimeout(() => fail('proxy tunnel timeout (' + timeoutMs + 'ms)'), timeoutMs);
    const onChunk = (chunk) => {
      if (settled) return;
      acc += chunk.toString('latin1');
      const idx = acc.indexOf('\r\n\r\n');
      if (idx < 0) return; // 继续等分片
      const head = acc.slice(0, idx);
      if (!/^HTTP\/1\.[01] 200/.test(head)) { clearTimeout(to); return fail('CONNECT rejected: ' + head.split('\r\n')[0].slice(0, 80)); }
      sock.removeListener('data', onChunk);
      const rest = acc.slice(idx + 4);
      if (rest.length) sock.unshift(Buffer.from(rest, 'latin1'));
      const tlsSock = tls.connect({ socket: sock, servername: host, ALPNProtocols: ['http/1.1'] }, () => {
        if (settled) return;
        settled = true; clearTimeout(to); resolve(tlsSock);
      });
      tlsSock.on('error', (e) => { clearTimeout(to); if (!settled) { settled = true; reject(e); } });
    };
    sock.on('data', onChunk);
    sock.on('error', (e) => { clearTimeout(to); fail('proxy tcp error: ' + e.message, e); });
    sock.write('CONNECT ' + host + ':' + port + ' HTTP/1.1\r\nHost: ' + host + ':' + port + '\r\n\r\n');
  });
}

function httpsViaTunnel(urlObj, init, timeoutMs) {
  const method = ((init && init.method) || 'GET').toUpperCase();
  let bodyBuf = null;
  const b = init && init.body;
  if (b != null) {
    if (b instanceof URLSearchParams) bodyBuf = Buffer.from(b.toString(), 'utf8');
    else if (typeof b === 'string') bodyBuf = Buffer.from(b, 'utf8');
    else if (Buffer.isBuffer(b)) bodyBuf = b;
    else if (b instanceof Uint8Array) bodyBuf = Buffer.from(b);
    else return Promise.reject(new Error('unsupported body type for oauth proxy: ' + (b && b.constructor && b.constructor.name)));
  }
  const perProxyMs = Math.max(8000, Math.floor(timeoutMs / PROXY_LIST.length));
  const errors = [];
  const attempt = (idx) => {
    if (idx >= PROXY_LIST.length) { const err = new Error('all oauth proxies failed: ' + errors.join(' | ')); err.aggregated = errors.slice(); return Promise.reject(err); }
    const proxyUrl = PROXY_LIST[idx];
    return openTunnel(urlObj.hostname, Number(urlObj.port || 443), perProxyMs, proxyUrl).then((sock) => new Promise((resolve, reject) => {
      const headers = {};
      const src = (init && init.headers) || {};
      try {
        if (typeof src.forEach === 'function' && !(src instanceof URLSearchParams) && !Array.isArray(src) && typeof src !== 'string') {
          // Headers / plain object
          src.forEach((v, k) => { headers[k] = v; });
          if (src instanceof Headers) { /* forEach 已覆盖 */ }
        }
        Object.assign(headers, !Array.isArray(src) && typeof src !== 'string' && typeof src.forEach !== 'function' ? src : {});
        if (Array.isArray(src)) src.forEach(([k, v]) => headers[k] = v);
      } catch (e) { /* 兜底 */ }
      headers['host'] = urlObj.host;
      if (bodyBuf) headers['content-length'] = String(bodyBuf.length);
      const req = http.request({
        createConnection: () => sock,
        method, path: (urlObj.pathname || '/') + (urlObj.search || ''), headers, agent: false,
      }, (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const text = Buffer.concat(chunks).toString('utf8');
          const h = new Headers();
          for (const [k, v] of Object.entries(res.headers)) {
            if (Array.isArray(v)) v.forEach((x) => h.append(k, x));
            else if (v != null) h.set(k, v);
          }
          resolve(new Response(method === 'HEAD' ? null : text, { status: res.statusCode, statusText: res.statusMessage, headers }));
        });
      });
      req.setTimeout(perProxyMs, () => { req.destroy(new Error('oauth https request timeout via ' + proxyUrl)); });
      req.on('error', (e) => { try { sock.destroy(); } catch (_) {} reject(e.cause || e); });
      if (bodyBuf) req.write(bodyBuf);
      req.end();
    })).catch((e) => {
      const msg = (e && (e.message || e.code)) || (e && e.errors && e.errors.map(x => x.code || x.message).join('+')) || String(e);
      errors.push(proxyUrl + ': ' + msg);
      console.warn(`[google-oauth-proxy] via ${proxyUrl} failed: ${msg}; trying next`);
      return attempt(idx + 1);
    });
  };
  return attempt(0);
}

globalThis.fetch = function patchedFetch(input, init) {
  let urlStr = null;
  try { urlStr = typeof input === 'string' ? input : (input && input.url) || String(input); } catch (e) {}
  let u = null;
  try { u = new URL(urlStr); } catch (e) {}
  if (u && TARGET_HOSTS.has(u.hostname)) {
    const t0 = Date.now();
    return httpsViaTunnel(u, init, 25000).then((res) => {
      console.log(`[google-oauth-proxy] ${u.pathname} ${res.status} ${Date.now() - t0}ms`);
      return res;
    }).catch((e) => {
      console.warn(`[google-oauth-proxy] all proxies failed (${(e && e.message) || e}); fallback direct`);
      return origFetch(input, init);
    });
  }
  return origFetch(input, init);
};
console.log(`[google-oauth-proxy] active: ${[...TARGET_HOSTS].join(',')} -> ${PROXY_LIST.join(' , ')}`);
