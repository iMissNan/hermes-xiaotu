const axios = require('axios');
const logger = require('../src/logger');

/**
 * 多源换源模块（2026-09）：GD音乐台 + 酷狗 + 酷我 + QQ + 咪咕
 * 任一源返回完整URL即为成功，全部失败返回null
 */
module.exports = {
  async unblock(id) {
    const sources = [
      // 1. GD音乐台（主源，FLAC优先）
      async () => {
        const res = await axios.get(
          `https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id=${id}&br=999`,
          { timeout: 15000 }
        );
        const d = res.data;
        if (d && typeof d === 'object' && d.url && d.url.includes('http')) return d.url;
        logger.warn(`gdmusic bad response: ${JSON.stringify(d).slice(0, 150)}`);
        return null;
      },
      // 2. 酷狗（@unblockneteasemusic 内置源）
      async () => {
        try {
          const { match } = require('../../../@unblockneteasemusic/server/src/provider/match');
          const { find } = require('../../../@unblockneteasemusic/server/src/provider/find');
          const data = await find(id);
          const result = await match(id, null, data);
          if (result && result.url) return result.url;
        } catch (e) {
          logger.warn(`kugou/kuwo/qq/migu match failed for ${id}: ${e.message}`);
        }
        return null;
      },
      // 3. 直接调用酷狗源（备用）
      async () => {
        const res = await axios.get('https://music.163.com/api/song/enhance/player/url', {
          params: { ids: `[${id}]`, br: 320000 },
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            Referer: 'https://music.163.com',
          },
          timeout: 10000,
        });
        const d = res.data;
        if (d && d.data && d.data[0] && d.data[0].url) return d.data[0].url;
        return null;
      },
    ];

    for (let i = 0; i < sources.length; i++) {
      try {
        const url = await sources[i]();
        if (url && url.startsWith('http')) {
          logger.info(`unblock success for ${id} from source ${i}`);
          return url;
        }
      } catch (e) {
        logger.warn(`unblock source ${i} failed for ${id}: ${e.message || e.code}`);
      }
    }

    return null;
  },
};