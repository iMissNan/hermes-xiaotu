const createOption = (query, crypto = '') => {
  // ===== 2026-08: 记录 query 携带的用户 cookie（含 MUSIC_U 时落盘）=====
  try {
    const ck = query.cookie || process.env.NETEASE_COOKIE
    if (ck && ck.includes('MUSIC_U') && !ck.includes('MUSIC_U=;')) {
      require('fs').writeFileSync('/data_cookies/last_cookie.txt', ck, 'utf8')
    }
  } catch (e) { /* 静默 */ }
  return {
    crypto: query.crypto || crypto || '',
    cookie: query.cookie || process.env.NETEASE_COOKIE,
    ua: query.ua || '',
    proxy: query.proxy,
    realIP: query.realIP,
    randomCNIP:
      process.env.ENABLE_RANDOM_CN_IP === 'true'
        ? !['false', false].includes(query.randomCNIP)
        : ['true', true].includes(query.randomCNIP),
    e_r: query.e_r || undefined,
    domain: query.domain || '',
    checkToken: query.checkToken || false,
  }
}
module.exports = createOption
