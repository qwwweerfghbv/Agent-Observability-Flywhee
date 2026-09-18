// 趋势折线图（SDD §5.10.2）：自绘 SVG，零第三方依赖（规避离线 npm 安装风险）。
// 支持变更竖线（markers）叠加，用于"指标拐点 vs 变更事件"关联分析。

export interface TrendPoint {
  label: string;
  value: number | null;
}

export interface TrendMarker {
  index: number;
  label?: string;
}

interface Props {
  points: TrendPoint[];
  markers?: TrendMarker[];
  height?: number;
  unit?: string;
  color?: string;
}

export default function TrendChart({
  points,
  markers = [],
  height = 160,
  unit = '',
  color = '#2563eb',
}: Props) {
  const W = 640;
  const H = height;
  const padL = 40;
  const padR = 12;
  const padT = 12;
  const padB = 24;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const vals = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (vals.length === 0) {
    return <div className="py-8 text-center text-xs text-gray-400">暂无趋势数据</div>;
  }
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const n = points.length;
  const xAt = (i: number) => padL + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const yAt = (v: number) => padT + innerH - ((v - min) / span) * innerH;

  // 折线路径（跳过 null 点，分段绘制）
  let d = '';
  let pen = false;
  points.forEach((p, i) => {
    if (p.value === null) {
      pen = false;
      return;
    }
    const x = xAt(i).toFixed(1);
    const y = yAt(p.value).toFixed(1);
    d += `${pen ? 'L' : 'M'}${x},${y} `;
    pen = true;
  });

  const yTicks = [max, (max + min) / 2, min];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }} role="img">
      {/* Y 轴网格 + 刻度 */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={yAt(t)} x2={W - padR} y2={yAt(t)} stroke="#eef2f7" strokeWidth="1" />
          <text x={4} y={yAt(t) + 3} fontSize="9" fill="#9ca3af">
            {Math.round(t)}
            {unit}
          </text>
        </g>
      ))}
      {/* 变更竖线 */}
      {markers.map((m, i) => (
        <g key={`m${i}`}>
          <line
            x1={xAt(m.index)}
            y1={padT}
            x2={xAt(m.index)}
            y2={padT + innerH}
            stroke="#f59e0b"
            strokeWidth="1"
            strokeDasharray="3 2"
          />
          {m.label && (
            <text x={xAt(m.index) + 2} y={padT + 8} fontSize="8" fill="#b45309">
              {m.label}
            </text>
          )}
        </g>
      ))}
      {/* 折线 */}
      <path d={d.trim()} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
      {/* 数据点 */}
      {points.map((p, i) =>
        p.value === null ? null : (
          <circle key={i} cx={xAt(i)} cy={yAt(p.value)} r="2" fill={color}>
            <title>{`${p.label}: ${p.value}${unit}`}</title>
          </circle>
        ),
      )}
      {/* X 轴首尾标签 */}
      {n > 0 && (
        <>
          <text x={padL} y={H - 6} fontSize="9" fill="#9ca3af">
            {points[0].label}
          </text>
          <text x={W - padR} y={H - 6} fontSize="9" fill="#9ca3af" textAnchor="end">
            {points[n - 1].label}
          </text>
        </>
      )}
    </svg>
  );
}
