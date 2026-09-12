// 歌曲链接（自动解灰增强版 2026-08：VIP/灰歌试听 → 自动换 gdmusic 完整版）
const createOption = require('../util/option.js')

module.exports = async (query, request) => {
  const ids = String(query.id).split(',')
  const data = {
    ids: JSON.stringify(ids),
    br: parseInt(query.br || 999000),
  }
  const res = await request(
    `/api/song/enhance/player/url`,
    data,
    createOption(query),
  )
  // 根据id排序
  const result = res.body.data
  result.sort((a, b) => {
    return ids.indexOf(String(a.id)) - ids.indexOf(String(b.id))
  })

  // ===== 自动解灰增强：试听片段（time<60s）→ matchID 遍历音源模块换完整版 =====
  try {
    const { matchID } = require('@neteasecloudmusicapienhanced/unblockmusic-utils')
    const candidates = result.filter((it) => it && it.url && it.time && it.time < 60000)
    if (candidates.length > 0) {
      const detailRes = await request(
        `/api/v3/song/detail`,
        { c: '[' + candidates.map((it) => '{"id":' + it.id + '}').join(',') + ']' },
        createOption(query, 'weapi'),
      )
      const dtMap = {}
      for (const s of (detailRes.body.songs || [])) dtMap[s.id] = s.dt
      for (const it of candidates) {
        const fullDt = dtMap[it.id] || 0
        if (fullDt > 120000) { // 真实时长 > 2 分钟 → 45s 音频必是试听
          const m = await matchID(String(it.id))
          if (m && m.data && m.data.url && m.data.url.startsWith('http')) {
            it.url = m.data.url
            it.size = null
            it.br = 320000
            it.time = fullDt
            it.unblocked = true
          } else {
            // 2026-09-02 修复：换源失败时把 time 改为真实时长，
            // 前端不再因为"35秒试听片段"判定不可播而自动跳下一首。
            // 保留试听 URL（还能听30秒），但 time 用真实时长，不跳歌。
            it.time = fullDt
            logger.info(`unblock failed for ${it.id}, keep trial but fix time to ${fullDt}ms`)
          }
        }
        // 关键：清掉试听标记——前端见 freeTrialInfo 非 null 直接判"无法播放"
        // 无论解灰成败都清：成功=完整版可播，失败=至少能听试听片段
        if (it.freeTrialInfo) it.freeTrialInfo = null
      }
    }
  } catch (e) {
    // 解灰失败不影响原结果（保留试听片段）
  }

  // ===== 2026-09: 音频地址改写为同源代理（绕开客户端代理冲突 / 混合内容拦截）=====
  // 浏览器不再直连网易云 CDN（该地址会被客户端代理规则拦下导致 ERR_PROXY_CONNECTION_FAILED），
  // 全部改为 /proxy?u=<原始地址>，由服务器 nginx 中转取流，客户端只访问本站点。
  for (const it of result) {
    if (it && it.url && /^https?:\/\//.test(it.url)) {
      it.url = '/proxy?u=' + encodeURIComponent(it.url)
    }
  }

  return {
    status: 200,
    body: {
      code: 200,
      data: result,
    },
  }
}
