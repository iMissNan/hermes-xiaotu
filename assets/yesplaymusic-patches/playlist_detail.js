// 歌单详情
// 增强（2026-08）：清 fee/noCopyrightRcmd → 前端不置灰

const createOption = require('../util/option.js')
module.exports = (query, request) => {
  const data = {
    id: query.id,
    n: 100000,
    s: query.s || 8,
  }
  return request(`/api/v6/playlist/detail`, data, createOption(query)).then(
    (res) => {
      // ===== 解锁前端置灰（2026-08）=====
      try {
        const tracks = (res.body.playlist && res.body.playlist.tracks) || []
        for (const s of tracks) {
          if (s.fee) s.fee = 0
          if (s.privilege && s.privilege.fee) s.privilege.fee = 0
          if (s.noCopyrightRcmd) delete s.noCopyrightRcmd
          if (s.privilege && s.privilege.noCopyrightRcmd) delete s.privilege.noCopyrightRcmd
          if (s.privilege && s.privilege.st < 0) s.privilege.st = 0
        }
      } catch (e) { /* 保持原样 */ }
      return res
    },
  )
}
