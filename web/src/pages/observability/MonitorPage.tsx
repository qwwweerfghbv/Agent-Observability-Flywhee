// 视图②运行监控（SDD §5.10.1）：分层 SLO 红绿灯 + 指标窗口聚合 + 意图/状态分布。
// 数据源：GET /slo + GET /metrics（复用 monitor.aggregate / judge_slo）。
import { getObsMetrics, getObsSlo } from '../../lib/api';
import { useObsWindow, usePolling } from '../../hooks/useObservability';
import { Card, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import StatusLight from '../../components/observability/StatusLight';
import type { MetricsAggregate, MetricsResponse, SloResponse } from '../../types/observability';

const pct = (v?: number | null) => (v == null ? '—' : `${(v * 100).toFixed(2)}%`);
const ms = (v?: number | null) => (v == null ? '—' : `${Math.round(v)}ms`);

function rateTone(v?: number | null): string | undefined {
  if (v == null) return undefined;
  if (v > 0.05) return 'text-red-600';
  if (v > 0.01) return 'text-amber-500';
  return 'text-green-600';
}

/** 分布条形（intent/status/model）：按占比横向条 */
function DistBars({ title, dist }: { title: string; dist: Record<string, number> }) {
  const entries = Object.entries(dist ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const max = entries.length ? entries[0][1] : 1;
  return (
    <div>
      <div className="mb-2 text-xs font-medium text-gray-500">{title}</div>
      {entries.length === 0 ? (
        <div className="py-3 text-center text-xs text-gray-400">无数据</div>
      ) : (
        <div className="space-y-1.5">
          {entries.map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-xs">
              <span className="w-28 shrink-0 truncate text-gray-500" title={k}>
                {k}
              </span>
              <div className="h-3 flex-1 overflow-hidden rounded bg-gray-100">
                <div className="h-3 rounded bg-blue-400" style={{ width: `${(v / max) * 100}%` }} />
              </div>
              <span className="w-8 shrink-0 text-right tabular-nums text-gray-600">{v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MetricGrid({ agg }: { agg: MetricsAggregate }) {
  const stats: { label: string; value: string; tone?: string }[] = [
    { label: '请求数', value: String(agg.request_count ?? 0) },
    { label: '请求错误率', value: pct(agg.request_error_rate), tone: rateTone(agg.request_error_rate) },
    { label: '降级率', value: pct(agg.degraded_rate), tone: rateTone(agg.degraded_rate) },
    { label: '中断率', value: pct(agg.interrupted_rate) },
    { label: 'LLM 错误率', value: pct(agg.llm_error_rate), tone: rateTone(agg.llm_error_rate) },
    { label: 'TTFT P50', value: ms(agg.ttft_p50_ms) },
    { label: 'TTFT P95', value: ms(agg.ttft_p95_ms) },
    { label: '时长 P95', value: ms(agg.duration_p95_ms) },
    { label: 'delta 间隔中位', value: ms(agg.stream_gap_median_ms) },
    { label: 'Token 总量', value: String(agg.tokens_total ?? 0) },
    {
      label: '记忆错误率',
      value: pct(agg.memory_error_rate),
      tone: (agg.memory_error_count ?? 0) > 0 ? 'text-red-600' : 'text-green-600',
    },
    {
      label: '记忆警告数',
      value: String(agg.memory_warn_count ?? 0),
      tone: (agg.memory_warn_count ?? 0) > 0 ? 'text-amber-500' : undefined,
    },
    {
      label: '会话持久化失败',
      value: String(agg.session_persist_fail_count ?? 0),
      tone: (agg.session_persist_fail_count ?? 0) > 0 ? 'text-red-600' : undefined,
    },
    { label: '记忆裁剪次数', value: String(agg.memory_trim_events ?? 0) },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      {stats.map((st) => (
        <div key={st.label} className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
          <div className="text-xs text-gray-400">{st.label}</div>
          <div className={`mt-1 text-lg font-semibold tabular-nums ${st.tone ?? 'text-gray-800'}`}>
            {st.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function MonitorPage() {
  const { window } = useObsWindow();
  const slo = usePolling<SloResponse>(() => getObsSlo(window), 60000, [window]);
  const metrics = usePolling<MetricsResponse>(() => getObsMetrics(window), 60000, [window]);
  const sd = slo.data;
  const md = metrics.data;

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      {/* 分层 SLO */}
      <Card
        title={`分层 SLO 判定（窗口 ${window}）`}
        action={
          sd && (
            <Pill tone={sd.health_score >= 90 ? 'green' : sd.health_score >= 70 ? 'amber' : 'red'}>
              健康分 {sd.health_score}
            </Pill>
          )
        }
      >
        {slo.loading && !sd ? (
          <Skeleton className="h-40" />
        ) : slo.error || !sd ? (
          <ErrorCard onRetry={slo.refresh} />
        ) : sd.slo.length === 0 ? (
          <div className="py-6 text-center text-xs text-gray-400">窗口内暂无可判定的 SLO 数据</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400">
                  <th className="py-1.5 pr-2">状态</th>
                  <th className="pr-2">层</th>
                  <th className="pr-2">指标</th>
                  <th className="pr-2">目标</th>
                  <th className="text-right">实际</th>
                </tr>
              </thead>
              <tbody>
                {sd.slo.map((it, i) => (
                  <tr key={i} className="border-t border-gray-100">
                    <td className="py-1.5 pr-2">
                      <StatusLight status={it.state} size="sm" />
                    </td>
                    <td className="pr-2 text-gray-500">{it.layer}</td>
                    <td className="pr-2 text-gray-700">{it.metric}</td>
                    <td className="pr-2 text-gray-500">
                      {it.op} {it.value}
                    </td>
                    <td className="text-right tabular-nums text-gray-700">{it.actual ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {sd && (sd.critical_violations.length > 0 || sd.warning_violations.length > 0) && (
          <div className="mt-3 flex flex-wrap gap-2 border-t border-gray-100 pt-3 text-xs">
            {sd.critical_violations.map((v, i) => (
              <Pill key={`c${i}`} tone="red">
                严重 {v.metric}
              </Pill>
            ))}
            {sd.warning_violations.map((v, i) => (
              <Pill key={`w${i}`} tone="amber">
                警告 {v.metric}
              </Pill>
            ))}
          </div>
        )}
      </Card>

      {/* 指标聚合 */}
      <Card title="指标窗口聚合">
        {metrics.loading && !md ? (
          <Skeleton className="h-32" />
        ) : metrics.error || !md ? (
          <ErrorCard onRetry={metrics.refresh} />
        ) : (
          <MetricGrid agg={md.aggregate} />
        )}
      </Card>

      {/* 分布 */}
      {md?.aggregate && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card title="意图分布">
            <DistBars title="top intent" dist={md.aggregate.intent_dist} />
          </Card>
          <Card title="状态分布">
            <DistBars title="status" dist={md.aggregate.status_dist} />
          </Card>
          <Card title="模型分布">
            <DistBars title="model" dist={md.aggregate.model_dist} />
          </Card>
        </div>
      )}
    </div>
  );
}
