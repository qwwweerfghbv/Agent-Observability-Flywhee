// 视图⑦飞轮周报（SDD §5.10.1 / US-S5）：评测运行数 + 最新通过率 + BadCase 回流三态统计
// + 待评审 severity 分布。数据源：GET /weekly（缺失时后端即时生成）。
import { getObsWeekly } from '../../lib/api';
import { usePolling } from '../../hooks/useObservability';
import { Card, EmptyCard, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import type { WeeklyResponse } from '../../types/observability';

const SEV_TONE: Record<string, 'red' | 'amber' | 'blue' | 'gray'> = {
  critical: 'red',
  high: 'amber',
  medium: 'blue',
  low: 'gray',
};

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-4">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`mt-1 text-3xl font-bold tabular-nums ${tone ?? 'text-gray-800'}`}>{value}</div>
    </div>
  );
}

export default function WeeklyPage() {
  const w = usePolling<WeeklyResponse>(() => getObsWeekly(), 120000, []);
  const d = w.data;

  if (w.loading && !d) {
    return (
      <div className="p-6">
        <Skeleton className="h-72" />
      </div>
    );
  }
  if (w.error || !d || d.error) {
    return (
      <div className="p-6">
        <ErrorCard onRetry={w.refresh} />
      </div>
    );
  }

  const lr = d.latest_run;
  const passRate =
    d.latest_pass_rate != null ? `${(d.latest_pass_rate * 100).toFixed(1)}%` : '—';
  const passTone =
    d.latest_pass_rate == null
      ? 'text-gray-800'
      : d.latest_pass_rate >= 0.8
        ? 'text-green-600'
        : d.latest_pass_rate >= 0.6
          ? 'text-amber-600'
          : 'text-red-600';
  const sev = Object.entries(d.pending_by_severity ?? {}).sort(
    (a, b) => (SEV_TONE[a[0]] ? 0 : 1) - (SEV_TONE[b[0]] ? 0 : 1) || b[1] - a[1],
  );
  const totalProcessed = (d.badcase_merged ?? 0) + (d.badcase_discarded ?? 0);

  return (
    <div className="mx-auto max-w-5xl space-y-4 px-6 py-6">
      {/* 周期头部 */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-gray-800">🗓️ 飞轮周报 · {d.week}</h2>
          <p className="text-xs text-gray-400">生成于 {d.generated_at || '—'}</p>
        </div>
        <button
          type="button"
          onClick={w.refresh}
          className="rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50"
        >
          ↻ 刷新
        </button>
      </div>

      {/* 核心指标 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="评测运行数" value={d.eval_runs ?? 0} tone="text-blue-600" />
        <Stat label="最新通过率" value={passRate} tone={passTone} />
        <Stat
          label="待评审 BadCase"
          value={d.badcase_pending ?? 0}
          tone={(d.badcase_pending ?? 0) > 0 ? 'text-amber-600' : 'text-green-600'}
        />
        <Stat label="本周已处理" value={totalProcessed} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* 最新运行 */}
        <Card title="最新评测运行">
          {!lr ? (
            <EmptyCard title="本周暂无评测运行" hint="跑一次评测后此处汇总最新 run" />
          ) : (
            <dl className="space-y-1 text-xs">
              <Row k="run_id" v={lr.run_id} mono />
              <Row k="时间" v={lr.timestamp || '—'} />
              <Row k="版本" v={lr.agent_version || '—'} />
              <Row k="用例数" v={String(lr.total_cases)} />
              <Row k="通过率" v={`${(lr.pass_rate * 100).toFixed(1)}%`} />
              <div className="flex items-center justify-between gap-2 py-0.5">
                <dt className="text-gray-400">门禁</dt>
                <dd>
                  <Pill tone={lr.gate_passed ? 'green' : 'red'}>
                    {lr.gate_passed ? '通过' : '未过'}
                  </Pill>
                </dd>
              </div>
            </dl>
          )}
        </Card>

        {/* BadCase 回流飞轮 */}
        <Card title="BadCase 回流飞轮">
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-around rounded-lg bg-gray-50 py-3 text-center">
              <FlowNum n={d.badcase_pending ?? 0} label="待评审" tone="text-amber-600" />
              <span className="text-gray-300">→</span>
              <FlowNum n={d.badcase_merged ?? 0} label="已合入" tone="text-green-600" />
              <span className="text-gray-300">/</span>
              <FlowNum n={d.badcase_discarded ?? 0} label="已丢弃" tone="text-gray-500" />
            </div>
            <div>
              <div className="mb-1 text-gray-400">待评审 severity 分布</div>
              {sev.length === 0 ? (
                <div className="py-2 text-center text-gray-400">🎉 无待评审</div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {sev.map(([k, v]) => (
                    <Pill key={k} tone={SEV_TONE[k] ?? 'gray'}>
                      {k} {v}
                    </Pill>
                  ))}
                </div>
              )}
            </div>
            <p className="text-[11px] leading-5 text-gray-400">
              线上回流的 bad case 需人工评审后才合入评测集（D7），合入即驱动下一轮回归——形成
              「线上问题 → 评测用例 → 版本改进」的飞轮闭环。
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-gray-50 py-0.5">
      <dt className="shrink-0 text-gray-400">{k}</dt>
      <dd className={`truncate text-gray-700 ${mono ? 'font-mono' : ''}`} title={v}>
        {v}
      </dd>
    </div>
  );
}

function FlowNum({ n, label, tone }: { n: number; label: string; tone: string }) {
  return (
    <div className="px-2">
      <div className={`text-2xl font-bold tabular-nums ${tone}`}>{n}</div>
      <div className="mt-0.5 text-[11px] text-gray-400">{label}</div>
    </div>
  );
}
