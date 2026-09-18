// 视图④质量哨兵（SDD §5.10.1 / US-Q1~Q4）：抽样评分覆盖 + 红线/注入/敏感命中 +
// 质量标志分布 + 各维度均分。数据源：GET /quality（复用 quality.jsonl 聚合）。
import { getObsQuality } from '../../lib/api';
import { useObsWindow, usePolling } from '../../hooks/useObservability';
import { Card, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import type { QualityResponse } from '../../types/observability';

function Bars({ dist, max }: { dist: Record<string, number>; max?: number }) {
  const entries = Object.entries(dist ?? {}).sort((a, b) => b[1] - a[1]);
  const top = max ?? (entries.length ? entries[0][1] : 1);
  if (entries.length === 0) {
    return <div className="py-4 text-center text-xs text-gray-400">无数据</div>;
  }
  return (
    <div className="space-y-1.5">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 text-xs">
          <span className="w-32 shrink-0 truncate text-gray-500" title={k}>
            {k}
          </span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-gray-100">
            <div className="h-3 rounded bg-blue-400" style={{ width: `${(v / (top || 1)) * 100}%` }} />
          </div>
          <span className="w-10 shrink-0 text-right tabular-nums text-gray-600">{v}</span>
        </div>
      ))}
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${tone ?? 'text-gray-800'}`}>{value}</div>
    </div>
  );
}

export default function QualityPage() {
  const { window } = useObsWindow();
  const q = usePolling<QualityResponse>(() => getObsQuality(window), 60000, [window]);
  const d = q.data;

  if (q.loading && !d) {
    return (
      <div className="p-6">
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (q.error || !d || d.error) {
    return (
      <div className="p-6">
        <ErrorCard onRetry={q.refresh} />
      </div>
    );
  }

  const sampleRate = d.total_records > 0 ? (d.sampled_scored / d.total_records) * 100 : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      {/* 命中概览 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard label="质量记录总数" value={d.total_records} />
        <StatCard
          label="已抽样评分"
          value={`${d.sampled_scored}`}
          tone="text-blue-600"
        />
        <StatCard
          label="红线命中"
          value={d.red_line_hits}
          tone={d.red_line_hits > 0 ? 'text-red-600' : 'text-green-600'}
        />
        <StatCard
          label="注入命中"
          value={d.injection_hits}
          tone={d.injection_hits > 0 ? 'text-red-600' : 'text-green-600'}
        />
        <StatCard
          label="敏感信息命中"
          value={d.sensitive_hits}
          tone={d.sensitive_hits > 0 ? 'text-amber-500' : 'text-green-600'}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* 维度均分（0-100） */}
        <Card
          title="质量维度均分"
          action={<span className="text-xs text-gray-400">抽样率 {sampleRate.toFixed(1)}%</span>}
        >
          {Object.keys(d.dimension_avg ?? {}).length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-400">
              暂无抽样评分（L5 默认 10% 抽样，需有请求命中）
            </div>
          ) : (
            <div className="space-y-2">
              {Object.entries(d.dimension_avg)
                .sort((a, b) => a[1] - b[1])
                .map(([k, v]) => {
                  const tone = v >= 85 ? 'bg-green-500' : v >= 70 ? 'bg-amber-400' : 'bg-red-500';
                  return (
                    <div key={k} className="flex items-center gap-2 text-xs">
                      <span className="w-28 shrink-0 truncate text-gray-500" title={k}>
                        {k}
                      </span>
                      <div className="h-3 flex-1 overflow-hidden rounded bg-gray-100">
                        <div className={`h-3 rounded ${tone}`} style={{ width: `${Math.min(100, v)}%` }} />
                      </div>
                      <span className="w-10 shrink-0 text-right tabular-nums text-gray-700">
                        {v.toFixed(1)}
                      </span>
                    </div>
                  );
                })}
            </div>
          )}
        </Card>

        {/* 质量标志分布 */}
        <Card title="质量标志分布">
          {Object.keys(d.flag_dist ?? {}).length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-400">✅ 无质量标志命中</div>
          ) : (
            <Bars dist={d.flag_dist} />
          )}
        </Card>
      </div>

      {(d.red_line_hits > 0 || d.injection_hits > 0 || d.sensitive_hits > 0) && (
        <Card title="安全提示">
          <div className="flex flex-wrap gap-2">
            {d.red_line_hits > 0 && <Pill tone="red">红线命中 {d.red_line_hits} 次</Pill>}
            {d.injection_hits > 0 && <Pill tone="red">注入命中 {d.injection_hits} 次</Pill>}
            {d.sensitive_hits > 0 && <Pill tone="amber">敏感信息 {d.sensitive_hits} 次</Pill>}
          </div>
          <p className="mt-2 text-xs text-gray-500">
            命中项已由安全扫描（L4/横切）标记，相关请求会进入评审队列，请前往评审台核实。
          </p>
        </Card>
      )}
    </div>
  );
}
