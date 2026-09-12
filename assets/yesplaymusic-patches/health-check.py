#!/usr/bin/env python3
"""YPM 源池每日健康巡检：
对 source-pool.json 每个启用的源，用测试歌逐源验证"能否出真音频"，
死源标记 dead（服务端自动跳过），复活或首次验证通过标记 alive。
结果写回 source-pool.json（服务端每次请求都重读，无需重启）。
"""
import json, urllib.request, hashlib, socket, sys, datetime

POOL = __import__('os').path.expanduser('~/.local/opt/yesplaymusic/config/source-pool.json')
API = __import__('os').environ.get('YPM_HEALTH_API', 'http://<你的域名>:8660')
# 测试歌：可不可以(553755659, VIP曲) + 岁月神偷(28285910, 免费曲) 双探针
TEST_IDS = [553755659, 28285910]
TIMEOUT = 60
HEAD_BYTES = 262144  # 下载前 256KB 足够校验

def http_get(url, timeout=TIMEOUT, headers=None, max_bytes=HEAD_BYTES):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(max_bytes), r.headers

def test_source(name, stype, sid):
    """返回 (alive, detail)。逐类型测出直链并验证音频。"""
    try:
        if stype == 'official':
            status, body, _ = http_get(f'{API}/api/song/url?id={sid}', timeout=30)
            d = json.loads(body)
            it = (d.get('data') or [None])[0]
            u = it and it.get('url')
            if not u:
                return False, 'song/url 无 url'
            if u.startswith('/proxy?u='):
                u = urllib.parse.unquote(u.split('/proxy?u=')[1])
            elif u.startswith('/'):
                return False, f'相对路径无法验证: {u[:30]}'
            st, head, hdrs = http_get(u, headers={'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-262143'})
            ok = (st in (200, 206)) and (head[:4] in (b'fLaC',) or head[:3] == b'ID3' or b'mpeg' in hdrs.get('Content-Type','').encode())
            return ok, f'status={st} head={head[:4]!r}'
        if stype == 'unm':
            # UNM 源借道容器内引擎：验证引擎对该源至少能返回 URL
            srcname = name.replace('unm-', '')
            cmd = (
                "const match=require('@unblockneteasemusic/server');"
                "match('" + str(sid) + "',['" + srcname + "'])" +
                ".then(function(r){var u=r&&r.url?(Array.isArray(r.url)?r.url[0]:r.url):null;console.log(u||'NULL')})" +
                ".catch(function(){console.log('NULL')})"
            )
            out = subprocess_container_node(cmd)
            if not out or out == 'NULL':
                return False, '引擎无 URL'
            st, head, _ = http_get(out, headers={'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-262143'})
            # UNM kuwo 会返回 185336B 占位音（已知指纹），精确大小直接判死
            if len(head) == 185336:
                return False, '占位音 185336B'
            ok = st in (200, 206) and len(head) > 100000 and head[:3] != b'<ht'
            return ok, f'status={st} size={len(head)}'
        if stype == 'gdstudio':
            chan = name.replace('gds-', '')
            # 拿歌名
            status, body, _ = http_get(f'{API}/api/song/detail?ids={sid}', timeout=30)
            d = json.loads(body)
            song = (d.get('songs') or [None])[0]
            if not song:
                return False, 'song/detail 无结果'
            kw = urllib.parse.quote((song['name'] + ' ' + ' '.join(a['name'] for a in (song.get('ar') or song.get('artists') or []))).strip())
            agent = 'https'  # placeholder
            st_, body2, _ = http_get(f'https://music-api.gdstudio.xyz/api.php?types=search&source={chan}&name={kw}&count=2&br=999', timeout=30)
            arr = json.loads(body2)
            if not isinstance(arr, list) or not arr:
                return False, f'{chan} 搜索空'
            for cand in arr[:2]:
                try:
                    st3, body3, _ = http_get(f'https://music-api.gdstudio.xyz/api.php?types=url&source={chan}&id={cand["id"]}&br=999', timeout=30)
                    u = json.loads(body3).get('url')
                    if not u:
                        continue
                    st4, head, _ = http_get(u, headers={'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-262143'})
                    if st4 in (200, 206) and head[:3] != b'<ht' and head[:3] != b'{"c':
                        return True, f'status={st4} head={head[:4]!r}'
                except Exception:
                    continue
            return False, f'{chan} 无可用 URL'
        if stype == 'community':
            status, body, _ = http_get(f'https://cue.me/meta/song?url=netease_{sid}', timeout=30)
            u = None
            if isinstance(body, bytes) and body[:1] in (b'{', b'['):
                try:
                    u = json.loads(body).get('url')
                except Exception:
                    u = None
            if not u:
                return False, '社区源无 URL'
            st, head, _ = http_get(u, headers={'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-262143'})
            return (st in (200, 206) and head[:3] != b'<ht'), f'status={st}'
        return False, f'未知类型 {stype}'
    except Exception as e:
        return False, f'{type(e).__name__}: {str(e)[:60]}'

def subprocess_container_node(code):
    """在容器里跑一段 node 代码，返回 stdout.strip()"""
    import subprocess
    API_DIR = '/usr/local/lib/node_modules/@neteasecloudmusicapienhanced/api'
    r = subprocess.run(
        ['sudo', 'docker', 'exec', '-w', API_DIR, 'yesplaymusic', 'node', '-e', code],
        capture_output=True, text=True, timeout=90,
    )
    lines = [l.strip() for l in (r.stdout + '\n' + r.stderr).splitlines()
             if l.strip().startswith('http')]
    return lines[-1] if lines else None

def main():
    import urllib.parse  # noqa
    with open(POOL) as f:
        pool = json.load(f)
    health = pool.setdefault('healthStatus', {})
    print(f"巡检开始 {datetime.datetime.now().isoformat(timespec='seconds')}")
    for s in pool['sources']:
        if not s.get('enabled'):
            health[s['name']] = 'disabled'
            continue
        # 双探针：任一歌通即 alive
        alive, detail = False, ''
        for sid in TEST_IDS:
            alive, detail = test_source(s['name'], s['type'], sid)
            if alive:
                break
        old = health.get(s['name'])
        health[s['name']] = 'alive' if alive else 'dead'
        mark = '✓' if alive else '✗'
        changed = f"（{old}→{health[s['name']]}）" if old and old != health[s['name']] else ''
        print(f"  {mark} {s['name']:<14} {detail} {changed}")
    pool['lastHealthCheck'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    with open(POOL, 'w') as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    alive_n = sum(1 for v in health.values() if v == 'alive')
    print(f"巡检完成：存活 {alive_n}/{sum(1 for s in pool['sources'] if s['enabled'])}")

if __name__ == '__main__':
    main()
