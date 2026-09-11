// 10Router 补丁 v4：自动扫描全部 chunk，强制 legacy/chat 两条链路 strictProxy
// 用法: docker cp 本文件进容器 && docker exec 10router node /tmp/strict-proxy.cjs && docker restart 10router
// 幂等；镜像升级后 chunk 哈希名会变，本脚本按锚点内容自适应定位，无需改路径。
const fs = require('fs');
const dir = '/app/.next/server/chunks';

const TARGETS = [
  // 聊天主链路: 手搓 proxyOptions 缺 strictProxy → 代理失败会回落裸连挂死
  { name: 'chat-proxyOptions',
    old: 'vercelRelayUrl:c?.providerSpecificData?.vercelRelayUrl||""}',
    neu: 'vercelRelayUrl:c?.providerSpecificData?.vercelRelayUrl||"",strictProxy:!0}' },
  // legacy 解析分支: 同样漏接
  { name: 'legacy-branch',
    old: 'return{source:"legacy",proxyPoolId:c||null,proxyPool:null,...f}',
    neu: 'return{source:"legacy",proxyPoolId:c||null,proxyPool:null,...f,strictProxy:!0}' },
];

let patched = 0, already = 0, missing = 0;
for (const f of fs.readdirSync(dir)) {
  if (!f.endsWith('.js')) continue;
  const fp = dir + '/' + f;
  let s = fs.readFileSync(fp, 'utf8');
  let changed = false;
  for (const t of TARGETS) {
    const cntOld = s.split(t.old).length - 1;
    const cntNew = s.split(t.neu).length - 1;
    if (cntNew > 0 && cntOld === 0) { already += cntNew; continue; }
    if (cntOld > 0) {
      s = s.split(t.old).join(t.neu);
      patched += cntOld;
      changed = true;
      console.log(`${f}: ${t.name} x${cntOld} PATCHED`);
    }
  }
  if (changed) {
    fs.copyFileSync(fp, fp + '.bak-strictproxy');
    fs.writeFileSync(fp, s);
  }
}
if (!patched) console.log('PATCHED_TOTAL=0 (already=' + already + ') — 检查是否所有副本已打好');
else console.log('PATCHED_TOTAL=' + patched + ' already=' + already);
