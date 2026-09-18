// 耗时分解瀑布（SDD §5.10.2）：自绘 div 按比例宽度，最大段标红 "← 瓶颈"。
// 通用：调用方（TraceDrawer）从 timing 构造非重叠的顺序段传入。

export interface WaterfallSegment {
  label: string;
  value: number | null; // ms
  color?: string; // tailwind bg-* 类，缺省蓝色
}

interface Props {
  segments: WaterfallSegment[];
  unit?: string;
}

export default function Waterfall({ segments, unit = 'ms' }: Props) {
  const valid = segments.filter(
    (s): s is { label: string; value: number; color?: string } =>
      s.value !== null && s.value !== undefined && s.value > 0,
  );
  if (valid.length === 0) {
    return <div className="py-6 text-center text-xs text-gray-400">暂无耗时分解数据</div>;
  }
  const total = valid.reduce((a, s) => a + s.value, 0) || 1;
  const maxVal = Math.max(...valid.map((s) => s.value));

  return (
    <div className="space-y-3">
      {/* 堆叠总条：一眼看出各段占比 */}
      <div className="flex h-5 w-full overflow-hidden rounded bg-gray-100">
        {valid.map((s, i) => {
          const pct = (s.value / total) * 100;
          const isMax = s.value === maxVal;
          return (
            <div
              key={i}
              className={isMax ? 'bg-red-500' : (s.color ?? 'bg-blue-500')}
              style={{ width: `${pct}%` }}
              title={`${s.label}: ${s.value}${unit}（${pct.toFixed(0)}%）${isMax ? ' ← 瓶颈' : ''}`}
            />
          );
        })}
      </div>
      {/* 明细行：标签 + 比例条 + 数值 */}
      <div className="space-y-1.5">
        {valid.map((s, i) => {
          const pct = (s.value / total) * 100;
          const isMax = s.value === maxVal;
          return (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="w-20 shrink-0 text-gray-500">{s.label}</span>
              <div className="h-3 flex-1 overflow-hidden rounded bg-gray-100">
                <div
                  className={`h-3 rounded ${isMax ? 'bg-red-500' : (s.color ?? 'bg-blue-500')}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span
                className={`w-28 shrink-0 text-right tabular-nums ${
                  isMax ? 'font-semibold text-red-600' : 'text-gray-600'
                }`}
              >
                {s.value}
                {unit}
                {isMax ? ' ← 瓶颈' : ''}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
