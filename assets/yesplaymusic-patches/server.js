require('dotenv').config()
const fs = require('fs')
const path = require('path')
const express = require('express')
const request = require('./util/request')
const packageJSON = require('./package.json')
const exec = require('child_process').exec
const cache = require('./util/apicache').middleware
const { cookieToJson } = require('./util/index')
const fileUpload = require('express-fileupload')
const decode = require('safe-decode-uri-component')
const logger = require('./util/logger.js')
const { APP_CONF } = require('./util/config.json')

/**
 * The version check result.
 * @readonly
 * @enum {number}
 */
const VERSION_CHECK_RESULT = {
  FAILED: -1,
  NOT_LATEST: 0,
  LATEST: 1,
}

/**
 * @typedef {{
 *   identifier?: string,
 *   route: string,
 *   module: any
 * }} ModuleDefinition
 */

/**
 * @typedef {{
 *   port?: number,
 *   host?: string,
 *   checkVersion?: boolean,
 *   moduleDefs?: ModuleDefinition[]
 * }} NcmApiOptions
 */

/**
 * @typedef {{
 *   status: VERSION_CHECK_RESULT,
 *   ourVersion?: string,
 *   npmVersion?: string,
 * }} VersionCheckResult
 */

/**
 * @typedef {{
 *  server?: import('http').Server,
 * }} ExpressExtension
 */

/**
 * Get the module definitions dynamically.
 *
 * @param {string} modulesPath The path to modules (JS).
 * @param {Record<string, string>} [specificRoute] The specific route of specific modules.
 * @param {boolean} [doRequire] If true, require() the module directly.
 * Otherwise, print out the module path. Default to true.
 * @returns {Promise<ModuleDefinition[]>} The module definitions.
 *
 * @example getModuleDefinitions("./module", {"album_new.js": "/album/create"})
 */
async function getModulesDefinitions(
  modulesPath,
  specificRoute,
  doRequire = true,
) {
  const files = await fs.promises.readdir(modulesPath)
  const parseRoute = (/** @type {string} */ fileName) =>
    specificRoute && fileName in specificRoute
      ? specificRoute[fileName]
      : `/${fileName.replace(/\.js$/i, '').replace(/_/g, '/')}`

  const modules = files
    .reverse()
    .filter((file) => file.endsWith('.js'))
    .map((file) => {
      const identifier = file.split('.').shift()
      const route = parseRoute(file)
      const modulePath = path.join(modulesPath, file)
      const module = doRequire ? require(modulePath) : modulePath

      return { identifier, route, module }
    })

  return modules
}

/**
 * Check if the version of this API is latest.
 *
 * @returns {Promise<VersionCheckResult>} If true, this API is up-to-date;
 * otherwise, this API should be upgraded and you would
 * need to notify users to upgrade it manually.
 */
async function checkVersion() {
  return new Promise((resolve) => {
    exec('npm info NeteaseCloudMusicApiEnhanced version', (err, stdout) => {
      if (!err) {
        let version = stdout.trim()

        /**
         * @param {VERSION_CHECK_RESULT} status
         */
        const resolveStatus = (status) =>
          resolve({
            status,
            ourVersion: packageJSON.version,
            npmVersion: version,
          })

        resolveStatus(
          packageJSON.version < version
            ? VERSION_CHECK_RESULT.NOT_LATEST
            : VERSION_CHECK_RESULT.LATEST,
        )
      } else {
        resolve({
          status: VERSION_CHECK_RESULT.FAILED,
        })
      }
    })
  })
}

function parseCorsAllowOrigins(corsAllowOrigin) {
  if (!corsAllowOrigin) {
    return null
  }

  const origins = corsAllowOrigin
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean)

  return origins.length > 0 ? origins : null
}

function getCorsAllowOrigin(allowOrigins, requestOrigin) {
  if (!allowOrigins) {
    return requestOrigin || '*'
  }

  if (allowOrigins.includes('*')) {
    return '*'
  }

  if (requestOrigin && allowOrigins.includes(requestOrigin)) {
    return requestOrigin
  }

  return null
}

function createConsoleSpinner(message = '启动中') {
  if (!process.stdout.isTTY) {
    return {
      stop() {},
    }
  }

  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
  let index = 0
  process.stdout.write(`${frames[index]} ${message}...`)
  const timer = setInterval(() => {
    index = (index + 1) % frames.length
    process.stdout.write(`\r${frames[index]} ${message}...`)
  }, 80)

  return {
    stop() {
      clearInterval(timer)
      process.stdout.write(`\r✔ ${message} 完成。\n`)
    },
  }
}

/**
 * Construct the server of NCM API.
 *
 * @param {ModuleDefinition[]} [moduleDefs] Customized module definitions [advanced]
 * @returns {Promise<import("express").Express>} The server instance.
 */
async function constructServer(moduleDefs) {
  const app = express()
  const { CORS_ALLOW_ORIGIN } = process.env
  const allowOrigins = parseCorsAllowOrigins(CORS_ALLOW_ORIGIN)
  app.set('trust proxy', true)

  /**
   * Serving static files
   */
  app.use(express.static(path.join(__dirname, 'public')))
  /**
   * CORS & Preflight request
   */
  app.use((req, res, next) => {
    if (req.path !== '/' && !req.path.includes('.')) {
      const corsAllowOrigin = getCorsAllowOrigin(
        allowOrigins,
        req.headers.origin,
      )
      const shouldSetVaryHeader = corsAllowOrigin && corsAllowOrigin !== '*'
      res.set({
        'Access-Control-Allow-Credentials': true,
        ...(corsAllowOrigin
          ? { 'Access-Control-Allow-Origin': corsAllowOrigin }
          : {}),
        ...(shouldSetVaryHeader ? { Vary: 'Origin' } : {}),
        'Access-Control-Allow-Headers': 'X-Requested-With,Content-Type',
        'Access-Control-Allow-Methods': 'PUT,POST,GET,DELETE,OPTIONS',
        'Content-Type': 'application/json; charset=utf-8',
      })
    }
    req.method === 'OPTIONS' ? res.status(204).end() : next()
  })

  /**
   * 全局响应清理（2026-08）：所有接口返回的歌曲统一清置灰标记
   * 递归遍历，覆盖 search / recommend / top / personal_fm / artist / album / dailySongs 等一切结构
   */
  app.use((req, res, next) => {
    const origJson = res.json
    res.json = function (body) {
      try {
        const cleanSong = (s) => {
          if (!s || typeof s !== 'object') return
          if (s.fee) s.fee = 0
          if (s.noCopyrightRcmd) delete s.noCopyrightRcmd
          if (s.privilege && typeof s.privilege === 'object') {
            if (s.privilege.fee) s.privilege.fee = 0
            if (s.privilege.noCopyrightRcmd) delete s.privilege.noCopyrightRcmd
            if (s.privilege.st < 0) s.privilege.st = 0
          }
        }
        // 递归：歌曲/privileges 对象（有 id+name 或 id+fee/st）清理标记；数组/对象继续下钻
        const walk = (node) => {
          if (Array.isArray(node)) {
            node.forEach((item) => {
              if (item && typeof item === 'object') {
                if (
                  typeof item.id !== 'undefined' &&
                  (typeof item.name === 'string' ||
                    typeof item.fee !== 'undefined' ||
                    typeof item.st !== 'undefined')
                ) cleanSong(item)
                walk(item)
              }
            })
          } else if (node && typeof node === 'object') {
            Object.values(node).forEach(walk)
          }
        }
        walk(body)
      } catch (e) { /* 静默 */ }
      return origJson.call(this, body)
    }
    next()
  })

  /**
   * Cookie Parser
   */
  app.use((req, _, next) => {
    // ===== 2026-08: 记录用户 cookie 供本机验证（含 MUSIC_U 登录凭证时落盘）=====
    try {
      const hc = req.headers.cookie || ''
      if (hc.includes('MUSIC_U')) {
        require('fs').writeFileSync('/data_cookies/last_cookie.txt', hc, 'utf8')
      }
    } catch (e) { /* 静默 */ }
    req.cookies = {}
    //;(req.headers.cookie || '').split(/\s*;\s*/).forEach((pair) => { //  Polynomial regular expression //
    ;(req.headers.cookie || '').split(/;\s+|(?<!\s)\s+$/g).forEach((pair) => {
      let crack = pair.indexOf('=')
      if (crack < 1 || crack == pair.length - 1) return
      req.cookies[decode(pair.slice(0, crack)).trim()] = decode(
        pair.slice(crack + 1),
      ).trim()
    })
    next()
  })

  /**
   * Body Parser and File Upload
   */
  const MAX_UPLOAD_SIZE_MB = 500
  const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

  app.use(express.json({ limit: `${MAX_UPLOAD_SIZE_MB}mb` }))
  app.use(
    express.urlencoded({ extended: false, limit: `${MAX_UPLOAD_SIZE_MB}mb` }),
  )

  app.use(
    fileUpload({
      limits: {
        fileSize: MAX_UPLOAD_SIZE_BYTES,
      },
      useTempFiles: true,
      tempFileDir: require('os').tmpdir(),
      abortOnLimit: true,
      parseNested: true,
    }),
  )

  // ===== 2026-09: 音频流服务器中转（/proxy?u=目标URL，浏览器同源取流）=====
  // 浏览器不再直连网易云 CDN（客户端代理会拦导致 ERR_PROXY_CONNECTION_FAILED），
  // 改由本服务流式转发，支持 Range（音频拖动/分段加载）。放在缓存中间件之前，
  // 避免 apicache 干扰流式响应。
  app.get('/proxy', (req, res) => {
    // 手动解析原始查询参数，避免 Express qs 解析器把 %2B(+) 转成空格
    const rawQuery = req.url.split('?')[1] || ''
    const match = rawQuery.match(/(?:^|&)u=([^&]*)/)
    if (!match) return res.status(400).json({ code: 400, msg: 'missing url param' })
    const target = decodeURIComponent(match[1])
    if (!target || !/^https?:\/\//.test(target)) {
      return res.status(400).json({ code: 400, msg: 'invalid url' })
    }
    const axios = require('axios')
    const opts = {
      url: target,
      method: 'GET',
      responseType: 'stream',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
        Referer: 'http://music.163.com',
        Accept: '*/*',
      },
      timeout: 30000,
      maxRedirects: 5,
    }
    if (req.headers.range) opts.headers['Range'] = req.headers.range
    axios(opts).then((ares) => {
      res.status(ares.status)
      // 透传关键响应头（Content-Type 强制标准化：去掉 charset 后缀，规避 Chromium
      // "Media load rejected by URL safety check" 对畸形 MIME 的拒绝）
      for (const h of ['content-length', 'content-range', 'accept-ranges', 'last-modified', 'etag']) {
        if (ares.headers[h]) res.set(h, ares.headers[h])
      }
      const ct = (ares.headers['content-type'] || '').split(';')[0].trim().toLowerCase()
      res.set('Content-Type', /^audio\//.test(ct) ? ct : (ct || 'application/octet-stream'))
      ares.data.pipe(res)
    }).catch((err) => {
      if (!res.headersSent) res.status(502).json({ code: 502, msg: 'upstream error: ' + (err.message || err.code) })
      else res.end()
    })
  })

  // ===== 2026-09: 源池换源引擎（10+ 源，每日巡检自动摘除死源）=====
  const SOURCE_POOL_PATH = '/usr/src/app/config/source-pool.json'
  let sourcePool = null
  try { sourcePool = JSON.parse(require('fs').readFileSync(SOURCE_POOL_PATH, 'utf8')) } catch (e) { sourcePool = null }
  const getPool = () => {
    if (!sourcePool) { try { sourcePool = JSON.parse(require('fs').readFileSync(SOURCE_POOL_PATH, 'utf8')) } catch (e) { return { sources: [] } } }
    return sourcePool
  }
  const activeSources = () => {
    const pool = getPool()
    const health = pool.healthStatus || {}
    return (pool.sources || [])
      .filter((s) => s.enabled && health[s.name] !== 'dead')
      .sort((a, b) => (a.priority || 99) - (b.priority || 99))
  }

  // 各源类型 → 取音频 URL 的函数（返回 http(s) 直链或 null）
  const fetchSourceUrl = (src, id) => {
    const axios = require('axios')
    if (src.type === 'official') {
      // 网易云 song/url（容器 NETEASE_COOKIE 自动带 VIP）
      return axios.get('http://localhost:3000/song/url?id=' + id, { timeout: 20000 }).then((r) => {
        const it = (r.data && r.data.data && r.data.data[0]) || null
        const u = it && it.url ? String(it.url) : null
        if (!u) return null
        // /proxy?u=... 相对路径 → 解出内层真实 URL；否则补 localhost 前缀
        if (u.startsWith('/proxy?u=')) return decodeURIComponent(String(u).split('/proxy?u=')[1])
        if (u.startsWith('/')) return 'http://localhost:3000' + u
        return u
      }).catch(() => null)
    }
    if (src.type === 'unm') {
      // UNM 引擎：源名去掉 unm- 前缀
      return new Promise((resolve) => {
        try {
          const match = require('@unblockneteasemusic/server')
          match(id, [src.name.replace(/^unm-/, '')]).then((r) => {
            const u = r && r.url ? (Array.isArray(r.url) ? r.url[0] : r.url) : null
            resolve(u || null)
          }).catch(() => resolve(null))
        } catch (e) { resolve(null) }
      })
    }
    if (src.type === 'gdstudio') {
      // gdstudio 聚合：先按歌名搜（引擎内部信息不共享，直接用网易云 song/detail 拿歌名）
      const chan = src.name.replace(/^gds-/, '')
      return axios.get('http://localhost:3000/song/detail?ids=' + id, { timeout: 15000 }).then(async (r) => {
        const song = (r.data && r.data.songs && r.data.songs[0]) || null
        if (!song) return null
        const name = String(song.name || '')
        const artists = ((song.ar || song.artists || []).map((a) => a.name) || []).join(' ')
        const httpsAgent = new (require('https').Agent)({ family: 4 })
        const api = 'https://music-api.gdstudio.xyz/api.php'
        const s = await axios.get(api, { params: { types: 'search', source: chan, name: (name + ' ' + artists).trim(), count: 3, br: 999 }, timeout: 15000, httpsAgent })
        const arr = Array.isArray(s.data) ? s.data : []
        for (const cand of arr) {
          try {
            const u = await axios.get(api, { params: { types: 'url', source: chan, id: cand.id, br: 999 }, timeout: 15000, httpsAgent })
            if (u.data && u.data.url) return String(u.data.url)
          } catch (e) { /* 试下一个候选 */ }
        }
        return null
      }).catch(() => null)
    }
    if (src.type === 'community') {
      // 社区公共 API（cue.me/meta）——返回 JSON {url}
      return axios.get('https://cue.me/meta/song?url=netease_' + id, { timeout: 15000 }).then((r) => {
        const u = r.data && (r.data.url || r.data.data && r.data.data.url)
        return u ? String(u) : null
      }).catch(() => null)
    }
    return Promise.resolve(null)
  }

  // 下载校验（占位音指纹 + 体积）→ 真音频直接回传
  const streamValidated = (u, res) => {
    const pool = getPool()
    const BAD_MD5S = pool.placeholderMd5s || ['86e42315600b9137e26ad17d54f3d622']
    return new Promise((resolve) => {
      const lib = u.startsWith('https') ? require('https') : require('http')
      lib.get(u, { headers: { 'User-Agent': 'Mozilla/5.0', Referer: u.includes('kuwo') ? 'https://www.kuwo.cn/' : '' }, timeout: 30000 }, (mres) => {
        if (mres.statusCode !== 200) { mres.destroy(); return resolve(false) }
        const chunks = []
        mres.on('data', (c) => chunks.push(c))
        mres.on('end', () => {
          const buf = Buffer.concat(chunks)
          const md5 = require('crypto').createHash('md5').update(buf).digest('hex')
          if (BAD_MD5S.includes(md5) || buf.length < 200000) return resolve(false)
          const ct = (mres.headers['content-type'] || '').split(';')[0].trim().toLowerCase()
          res.set('Content-Type', /^audio\//.test(ct) ? ct : (/^\x66\x4c\x61\x43/.test(buf) ? 'audio/flac' : 'audio/mpeg'))
          res.set('Content-Length', String(buf.length))
          res.set('Accept-Ranges', 'none')
          res.end(buf)
          resolve(true)
        })
        mres.on('error', () => resolve(false))
      }).on('error', () => resolve(false))
    })
  }

  // 换源主流程：按优先级逐源尝试（含来源过滤 excludeOfficial）
  const switchSource = async (id, res, opts) => {
    const options = opts || {}
    const sources = activeSources().filter((s) => !(options.excludeOfficial && s.type === 'official'))
    for (const src of sources) {
      try {
        const u = await fetchSourceUrl(src, id)
        if (!u) continue
        const ok = await streamValidated(u, res)
        if (ok) {
          if (!res.headersSent) return
          console.log('[switch] id=' + id + ' 命中源: ' + src.name)
          return
        }
      } catch (e) { /* 下一源 */ }
    }
    if (!res.headersSent) res.status(404).json({ code: 404, msg: '全源池均未命中' })
  }

  // 换源接口：前端 loaderror / 手动换源按钮统一入口
  const switchHandler = (req, res) => {
    const id = String(req.query.id || '').replace(/\D/g, '')
    if (!id) return res.status(400).json({ code: 400, msg: 'missing id' })
    return switchSource(id, res)
  }
  app.get('/api/song/switch', switchHandler)
  app.get('/song/switch', switchHandler)

  // ===== 2026-09: 匿名播放入口接管（方案 A）=====
  // 前端匿名状态用 music.163.com/song/media/outer/url（302→网易云 CDN），
  // 该域名会被客户端代理拦截导致 loaderror 秒跳歌。此接口在服务器端跟随 302
  // 取到真实 mp3 并流式回传，浏览器全程只访问本站。
  const outerHandler = (req, res) => {
    const id = String(req.query.id || '').replace(/\D/g, '')
    if (!id) return res.status(400).json({ code: 400, msg: 'missing id' })
    const axios = require('axios')
    axios({
      url: 'https://music.163.com/song/media/outer/url?id=' + id,
      method: 'GET',
      responseType: 'stream',
      maxRedirects: 5,
      timeout: 30000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
        Referer: 'https://music.163.com',
        Accept: '*/*',
      },
    }).then((ares) => {
      // 网易云对无版权/VIP 歌返回两种占位响应：
      // ① text/html（106848B "暂无法播放"页面）② 固定 106848B 占位 mp3
      // 识别后直接 404，让前端 loaderror 跳下一首，不播占位内容
      const upCT = String(ares.headers['content-type'] || '').toLowerCase()
      const isAudio = upCT.includes('audio/')
      const isPlaceholder = String(ares.headers['content-length']) === '106848'
      if (!isAudio || isPlaceholder) {
        ares.data.destroy()
        // ===== 2026-09: 源池换源（播放失败自动走全源池）=====
        return switchSource(id, res)
      }
      res.status(ares.status)
      for (const h of ['content-length', 'content-range', 'accept-ranges', 'last-modified', 'etag']) {
        if (ares.headers[h]) res.set(h, ares.headers[h])
      }
      const ct = (ares.headers['content-type'] || '').split(';')[0].trim().toLowerCase()
      res.set('Content-Type', /^audio\//.test(ct) ? ct : (ct || 'application/octet-stream'))
      ares.data.pipe(res)
    }).catch((err) => {
      if (!res.headersSent) res.status(502).json({ code: 502, msg: 'outer upstream error: ' + (err.message || err.code) })
      else res.end()
    })
  }
  app.get('/api/song/outer', outerHandler)
  // nginx 把 /api/ 前缀剥掉转发，Node 实际收到 /song/outer
  app.get('/song/outer', outerHandler)

  /**
   * Cache
   */
  app.use(cache('2 minutes', (_, res) => res.statusCode === 200))
  // ===== 2026-08: 禁止浏览器/代理缓存 API 响应（防止用户看到旧数据导致"灰色残留"）=====
  app.use((req, res, next) => {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
    res.set('Pragma', 'no-cache')
    next()
  })

  /**
   * Special Routers
   */
  const special = {
    'daily_signin.js': '/daily_signin',
    'fm_trash.js': '/fm_trash',
    'personal_fm.js': '/personal_fm',
  }

  /**
   * Load every modules in this directory
   */
  const moduleDefinitions =
    moduleDefs ||
    (await getModulesDefinitions(path.join(__dirname, 'module'), special))

  for (const moduleDef of moduleDefinitions) {
    // Register the route.
    app.all(moduleDef.route, async (req, res) => {
      ;[req.query, req.body].forEach((item) => {
        // item may be undefined (some environments / middlewares).
        // Guard access to avoid "Cannot read properties of undefined (reading 'cookie')".
        if (item && typeof item.cookie === 'string') {
          item.cookie = cookieToJson(decode(item.cookie))
        }
      })

      let query = Object.assign(
        {},
        { cookie: req.cookies },
        req.query,
        req.body,
        req.files,
      )

      try {
        let usedCrypto = ''
        const moduleResponse = await moduleDef.module(query, (...params) => {
          const obj = [...params]
          const options = obj[2] || {}
          usedCrypto = options.crypto || ''
          let ip = ''

          if (options.randomCNIP) {
            ip = global.cnIp
          } else {
            ip = req.ip

            if (ip.substring(0, 7) == '::ffff:') {
              ip = ip.substring(7)
            }
            if (ip == '::1') {
              ip = global.cnIp
            }
          }

          obj[2] = {
            ...options,
            ip,
          }

          return request(...obj)
        })
        const displayCrypto = usedCrypto || (APP_CONF.encrypt ? 'eapi' : 'api')
        logger.info(
          `Request Success: [${displayCrypto}] ${decode(req.originalUrl)}`,
        )

        // 夹带私货部分：如果开启了通用解锁，并且是获取歌曲URL的接口，则尝试解锁（如果需要的话）ヾ(≧▽≦*)o
        if (
          req.baseUrl === '/song/url/v1' &&
          process.env.ENABLE_GENERAL_UNBLOCK === 'true'
        ) {
          const song = moduleResponse.body.data[0]
          if (
            song.freeTrialInfo !== null ||
            !song.url ||
            [1, 4].includes(song.fee)
          ) {
            const {
              matchID,
            } = require('@neteasecloudmusicapienhanced/unblockmusic-utils')
            logger.info('Starting unblock(uses general unblock):', req.query.id)
            const result = await matchID(req.query.id)
            song.url = result.data.url
            song.freeTrialInfo = null
            logger.info('Unblock success! url:', song.url)
          }
          if (song.url && song.url.includes('kuwo')) {
            const proxy = process.env.PROXY_URL
            const useProxy = process.env.ENABLE_PROXY || 'false'
            if (useProxy === 'true' && proxy) {
              song.proxyUrl = proxy + song.url
            }
          }
        }

        const cookies = moduleResponse.cookie
        if (!query.noCookie) {
          if (Array.isArray(cookies) && cookies.length > 0) {
            if (req.protocol === 'https') {
              // Try to fix CORS SameSite Problem
              res.append(
                'Set-Cookie',
                cookies.map((cookie) => {
                  return cookie + '; SameSite=None; Secure'
                }),
              )
            } else {
              res.append('Set-Cookie', cookies)
            }
          }
        }
        if (moduleResponse.redirectUrl) {
          res.redirect(moduleResponse.status || 302, moduleResponse.redirectUrl)
          return
        }

        res.status(moduleResponse.status).send(moduleResponse.body)
      } catch (/** @type {*} */ moduleResponse) {
        logger.error(`${decode(req.originalUrl)}`, {
          status: moduleResponse.status,
          body: moduleResponse.body,
        })
        if (!moduleResponse.body) {
          res.status(404).send({
            code: 404,
            data: null,
            msg: 'Not Found',
          })
          return
        }
        if (moduleResponse.body.code == '301')
          moduleResponse.body.msg = '需要登录'
        if (!query.noCookie) {
          res.append('Set-Cookie', moduleResponse.cookie)
        }

        res.status(moduleResponse.status).send(moduleResponse.body)
      }
    })
  }

  return app
}

/**
 * Serve the NCM API.
 * @param {NcmApiOptions} options
 * @returns {Promise<import('express').Express & ExpressExtension>}
 */
async function serveNcmApi(options) {
  const port = Number(options.port || process.env.PORT || '3000')
  const host = options.host || process.env.HOST || ''

  const spinner = createConsoleSpinner('服务启动中')

  const checkVersionSubmission =
    options.checkVersion &&
    checkVersion().then(({ npmVersion, ourVersion, status }) => {
      if (status == VERSION_CHECK_RESULT.NOT_LATEST) {
        logger.warn(
          `最新版本: ${npmVersion}, 当前版本: ${ourVersion}, 请及时更新`,
        )
      }
    })
  const constructServerSubmission = constructServer(options.moduleDefs)

  const [_, app] = await Promise.all([
    checkVersionSubmission,
    constructServerSubmission,
  ])

  spinner.stop()

  /** @type {import('express').Express & ExpressExtension} */
  const appExt = app
  appExt.server = app.listen(port, host, () => {
    console.log(`
  ╔═╗╔═╗╦    ╔═╗╔╗╔╦ ╦╔═╗╔╗╔╔═╗╔═╗╔╦╗
  ╠═╣╠═╝║    ║╣ ║║║╠═╣╠═╣║║║║  ║╣  ║║
  ╩ ╩╩  ╩    ╚═╝╝╚╝╩ ╩╩ ╩╝╚╝╚═╝╚═╝═╩╝
    `)
    logger.info(
      `Server started successfully @ http://${host ? host : 'localhost'}:${port}`,
    )
  })

  return appExt
}

module.exports = {
  serveNcmApi,
  getModulesDefinitions,
}
