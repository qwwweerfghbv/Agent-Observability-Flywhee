// 一次性协议核查脚本：确认 ai@7 客户端期望的 UI Message Stream 协议版本
const fs = require('fs');
const path = require('path');

const distPath = path.join(__dirname, 'node_modules', 'ai', 'dist', 'index.js');
const src = fs.readFileSync(distPath, 'utf8');

const needles = ['x-vercel-ai-ui-message-stream', 'ui-message-stream', 'text-delta', 'data-card'];
for (const n of needles) {
  let idx = src.indexOf(n);
  let count = 0;
  const windows = [];
  while (idx !== -1 && count < 3) {
    windows.push(src.slice(Math.max(0, idx - 30), idx + n.length + 30).replace(/\s+/g, ' '));
    idx = src.indexOf(n, idx + 1);
    count++;
  }
  const total = src.split(n).length - 1;
  console.log(`\n[${n}] 命中 ${total} 次`);
  windows.forEach((w, i) => console.log(`  #${i + 1}: ...${w}...`));
}
