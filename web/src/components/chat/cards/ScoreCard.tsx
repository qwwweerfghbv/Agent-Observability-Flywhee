import type { ScoreCardData } from '../../../types/models';

// 5 个评分维度（顺序即雷达图顶点顺序，从正上方开始顺时针）
const DIMS: Array<{ key: keyof ScoreCardData['dimensions']; label: string }> = [
  { key: 'skill', label: '技能' },
  { key: 'experience', label: '经验' },
  { key: 'salary', label: '薪资' },
  { key: 'stability', label: '稳定性' },
  { key: 'growth', label: '前景' },
];

const CX = 120;
const CY = 105;
const R = 66;
const N = DIMS.length;

/** 极坐标 → 直角坐标：ratio 为 0~1（占满半径比例） */
function polar(i: number, ratio: number): [number, number] {
  const angle = (-90 + (i * 360) / N) * (Math.PI / 180);
  const r = R * Math.max(0, Math.min(1, ratio));
  return [CX + r * Math.cos(angle), CY + r * Math.sin(angle)];
}

/** 生成 polygon points：ratio 可为固定值（网格环）或按维度的函数（数据多边形） */
function toPoints(ratio: number | ((i: number) => number)): string {
  return DIMS.map((_, i) => {
    const rr = typeof ratio === 'number' ? ratio : ratio(i);
    const [x, y] = polar(i, rr);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

const LEVEL_STYLE: Record<string, string> = {
  A: 'bg-green-100 text-green-700 ring-green-300',
  B: 'bg-blue-100 text-blue-700 ring-blue-300',
  C: 'bg-amber-100 text-amber-700 ring-amber-300',
  D: 'bg-red-100 text-red-700 ring-red-300',
};

/** 岗位评分卡片：SVG 五维雷达图 + 等级徽章 + 优势/不足/建议 + AI 替代风险 */
export default function ScoreCard({ data }: { data: ScoreCardData }) {
  const dims = data.dimensions;
  const levelClass = LEVEL_STYLE[data.score_level] ?? 'bg-gray-100 text-gray-600 ring-gray-300';
  const risk = typeof data.ai_replacement_risk === 'number' ? data.ai_replacement_risk : null;

  return (
    <div className="my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">📊 岗位匹配评分</h3>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ${levelClass}`}>
          {data.score_level} 级
        </span>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-3xl font-bold text-blue-600">{Math.round(data.total_score)}</span>
        <span className="text-sm text-gray-400">/ 100</span>
      </div>

      {/* 五维雷达图 */}
      <svg viewBox="0 0 240 210" className="mx-auto mt-2 w-full max-w-[280px]">
        {[0.25, 0.5, 0.75, 1].map((ring) => (
          <polygon key={ring} points={toPoints(ring)} fill="none" stroke="#e5e7eb" strokeWidth="1" />
        ))}
        {DIMS.map((d, i) => {
          const [x, y] = polar(i, 1);
          return <line key={d.key} x1={CX} y1={CY} x2={x} y2={y} stroke="#e5e7eb" strokeWidth="1" />;
        })}
        <polygon
          points={toPoints((i) => (dims[DIMS[i].key] ?? 0) / 100)}
          fill="rgba(37,99,235,0.22)"
          stroke="rgba(37,99,235,0.9)"
          strokeWidth="2"
        />
        {DIMS.map((d, i) => {
          const [x, y] = polar(i, (dims[d.key] ?? 0) / 100);
          return <circle key={d.key} cx={x} cy={y} r="2.5" fill="#2563eb" />;
        })}
        {DIMS.map((d, i) => {
          const [x, y] = polar(i, 1.24);
          const anchor = x < CX - 6 ? 'end' : x > CX + 6 ? 'start' : 'middle';
          return (
            <text
              key={d.key}
              x={x}
              y={y}
              textAnchor={anchor}
              dominantBaseline="middle"
              fontSize="11"
              className="fill-gray-600"
            >
              {d.label} {Math.round(dims[d.key] ?? 0)}
            </text>
          );
        })}
      </svg>

      <div className="mt-3 space-y-2 text-sm">
        <ListBlock icon="✅" title="优势" tone="text-green-700" items={data.strengths} />
        <ListBlock icon="⚠️" title="不足" tone="text-amber-700" items={data.weaknesses} />
        <ListBlock icon="💡" title="建议" tone="text-blue-700" items={data.suggestions} />
      </div>

      {risk !== null && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-500">
            <span>🤖 AI 替代风险</span>
            <span>{risk}%</span>
          </div>
          <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
            <div
              className="h-2 rounded-full bg-gradient-to-r from-green-400 via-amber-400 to-red-500"
              style={{ width: `${Math.max(0, Math.min(100, risk))}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ListBlock({
  icon,
  title,
  tone,
  items,
}: {
  icon: string;
  title: string;
  tone: string;
  items: string[];
}) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div className={`font-medium ${tone}`}>
        {icon} {title}
      </div>
      <ul className="mt-0.5 space-y-0.5 pl-1 text-gray-600">
        {items.map((it, i) => (
          <li key={i} className="leading-5">
            • {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
