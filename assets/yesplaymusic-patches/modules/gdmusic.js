const axios = require('axios');
const logger = require('../src/logger');
const br = process.env.DISABLE_FLAC === 'true' ? 320 : 999;

/**
 * gdmusic 音源（GD音乐台）——网易云 VIP 歌曲完整版（320kbps / FLAC）
 * 2026-09-02 增强：GD音乐台超时/失败时，自动 fallback 到内置 UNM 多源
 * （酷狗/酷我/QQ/咪咕），任一源返回完整URL即为成功。
 */
const UNM_SRC = '/usr/local/lib/node_modules/@neteasecloudmusicapienhanced/api/node_modules/@unblockneteasemusic/server/src';

// 尝试从 UNM-Server 取完整版（酷狗/酷我等内置源）
async function tryUnm(id) {
  try {
    const { match, find } = require(UNM_SRC + '/provider/match');
    const findMod = require(UNM_SRC + '/provider/find');
    // find(id) 返回歌曲元数据；match 会遍历 DEFAULT_SOURCE（kugou/bodian/migu/ytdlp）
    const info = await (findMod.default || findMod)(id);
    const audioData = await match(id, null, info);
    if (audioData && audioData.url && audioData.url.startsWith('http')) {
      return audioData.url;
    }
  } catch (e) {
    logger.warn(`UNM multi-source failed for ${id}: ${e && e.message ? e.message : e}`);
  }
  return null;
}

module.exports = {
  async gdmusic(id) {
    // 先试 GD 音乐台（主源，FLAC）
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        const response = await axios.get(
          `https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id=${id}&br=${br}`,
          { timeout: 15000 },
        )
        const d = response.data
        if (d && typeof d === 'object' && d.url && d.url.includes('http')) {
          return d.url
        }
        logger.error(`gdmusic bad response (attempt ${attempt}): ${JSON.stringify(d).slice(0, 150)}`)
      } catch (error) {
        logger.error(
          `gdmusic error (attempt ${attempt}): ${error && error.message ? error.message : JSON.stringify(error)}`,
        )
      }
      if (attempt < 2) {
        await new Promise((r) => setTimeout(r, 800))
      }
    }

    // GD 失败 → fallback 到 UNM 多源（酷狗/酷我/QQ/咪咕）
    const unmUrl = await tryUnm(id)
    if (unmUrl) {
      logger.info(`gdmusic fallback to UNM multi-source for ${id}: ${unmUrl.slice(0, 80)}`)
      return unmUrl
    }

    return null
  },
}