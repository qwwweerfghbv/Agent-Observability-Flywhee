// delta 节奏柱状（SDD §5.10.2）：自绘 div，间隔 <threshold(默认5ms) 的柱标红。
// 可视化 stream_degraded（B2）：正常逐字输出间隔应远大于 5ms，密集 <5ms 说明
// 后端一次性 flush（伪流式）。后端未返回 delta_gaps 时优雅降级为空态。

interface Props {
  gaps: number[]; // 相邻 delta 的间隔（ms）
  threshold?: number; // 低于此值判为退化，默认 5ms
  height?: number;
}

export default function GapBars({ gaps, threshold = 5, height = 80 }: Props) {
  if (!gaps || gaps.length === 0) {
    return (
      <div className="py-6 text-center text-xs text-gray-400">
        暂无逐 delta 节奏数据（需后端返回 delta_gaps）
      </div>
    );
  }
  const max = Math.max(...gaps, threshold) || 1;
  const degraded = gaps.filter((g) => g < threshold).length;

  return (
    <div>
      <div className="flex items-end gap-px" style={{ height }}>
        {gaps.map((g, i) => {
          const h = Math.max(2, (g / max) * (height - 4));
          const bad = g < threshold;
          return (
            <div
              key={i}
              className={`flex-1 ${bad ? 'bg-red-500' : 'bg-blue-400'}`}
              style={{ height: h }}
              title={`#${i + 1}: ${g}ms${bad ? '（退化）' : ''}`}
            />
          );
        })}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[10px]">
        <span className="text-gray-400">{gaps.length} 个间隔 · 阈值 {threshold}ms</span>
        <span className={degraded > 0 ? 'font-medium text-red-600' : 'font-medium text-green-600'}>
          {degraded > 0 ? `${degraded} 个 <${threshold}ms（流式退化）` : '节奏正常'}
        </span>
      </div>
    </div>
  );
}
