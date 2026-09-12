// 通过传过来的歌单id拿到所有歌曲数据
// 支持传递参数limit来限制获取歌曲的数量 例如: /playlist/track/all?id=7044354223&limit=10
// 增强（2026-08）：清 fee/noCopyrightRcmd → 前端不置灰 → 播放时后端自动解灰

const createOption = require('../util/option.js')
module.exports = (query, request) => {
  const data = {
    id: query.id,
    n: 100000,
    s: query.s || 8,
  }
  let limit = parseInt(query.limit) || 1000
  let offset = parseInt(query.offset) || 0

  return request(`/api/v6/playlist/detail`, data, createOption(query)).then(
    (res) => {
      let trackIds = res.body.playlist.trackIds
      let idsData = {
        c:
          '[' +
          trackIds
            .slice(offset, offset + limit)
            .map((item) => '{"id":' + item.id + '}')
            .join(',') +
          ']',
      }

      return request(`/api/v3/song/detail`, idsData, createOption(query)).then(
        (res2) => {
          // ===== 解锁前端置灰（2026-08）：fee→0、删 noCopyrightRcmd =====
          try {
            const songs = res2.body.songs || []
            for (const s of songs) {
              if (s.fee) s.fee = 0
              if (s.privilege && s.privilege.fee) s.privilege.fee = 0
              if (s.noCopyrightRcmd) delete s.noCopyrightRcmd
              if (s.privilege && s.privilege.noCopyrightRcmd) delete s.privilege.noCopyrightRcmd
              if (s.privilege && s.privilege.st < 0) s.privilege.st = 0
            }
          } catch (e) { /* 保持原样 */ }
          return res2
        },
      )
    },
  )
}
