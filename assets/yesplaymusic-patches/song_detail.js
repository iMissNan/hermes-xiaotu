// 歌曲详情
// 增强（2026-08）：清 fee/noCopyrightRcmd → 前端不置灰
// 增强（2026-09）：所有 music.126.net CDN 地址改写为同源 /proxy → 浏览器永不直连网易云 CDN（规避客户端代理拦截）

const createOption = require('../util/option.js')
module.exports = (query, request) => {
  // 歌曲数量不要超过1000
  query.ids = query.ids.split(/\s*,\s*/)
  const data = {
    c: '[' + query.ids.map((id) => '{"id":' + id + '}').join(',') + ']',
  }
  return request(`/api/v3/song/detail`, data, createOption(query, 'weapi')).then(
    (res) => {
      // ===== 解锁前端置灰（2026-08）=====
      try {
        const songs = res.body.songs || []
        for (const s of songs) {
          if (s.fee) s.fee = 0
          if (s.privilege && s.privilege.fee) s.privilege.fee = 0
          if (s.noCopyrightRcmd) delete s.noCopyrightRcmd
          if (s.privilege && s.privilege.noCopyrightRcmd) delete s.privilege.noCopyrightRcmd
          if (s.privilege && s.privilege.st < 0) s.privilege.st = 0
        }
      } catch (e) { /* 保持原样 */ }

      // ===== 2026-09: CDN 地址改写为同源代理 =====
      // 递归遍历所有字符串字段，把 music.126.net / 126.net 的 http(s) 地址改写为 /proxy?u=<编码后原地址>
      // 覆盖：专辑封面 picUrl、歌手头像、MV、试听片段等一切网易云 CDN 资源
      try {
        const rewriteUrl = (s) => {
          if (typeof s !== 'string') return s
          if (/^https?:\/\/[^/]*music\.126\.net\//.test(s) || /^https?:\/\/[^/]*126\.net\//.test(s)) {
            return '/proxy?u=' + encodeURIComponent(s)
          }
          return s
        }
        const walk = (node) => {
          if (Array.isArray(node)) {
            for (let i = 0; i < node.length; i++) {
              const v = node[i]
              if (typeof v === 'string') node[i] = rewriteUrl(v)
              else if (v && typeof v === 'object') walk(v)
            }
          } else if (node && typeof node === 'object') {
            for (const k of Object.keys(node)) {
              const v = node[k]
              if (typeof v === 'string') node[k] = rewriteUrl(v)
              else if (v && typeof v === 'object') walk(v)
            }
          }
        }
        walk(res.body)
      } catch (e) { /* 静默 */ }

      return res
    },
  )
}
