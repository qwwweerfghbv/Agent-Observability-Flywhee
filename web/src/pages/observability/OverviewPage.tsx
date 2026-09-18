// 视图①飞轮总览（SDD §5.10.1）：健康分 + 七层状态灯 + 飞轮四环节 + 告警 + 最近变更。
// 数据源：GET /summary + GET /events（全部经聚合 API，D9）。
import { useNavigate } from 'react-router';
import { getObsEvents, getObsSummary } from '../../lib/api';
import { useObsWindow, usePolling } from '../../hooks/useObservability';
import { Card, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import StatusLight from '../../components/observability/StatusLight';
import type { EventsResponse, LayerStatus, SummaryResponse } from '../../types/observability';

// 与后端 memory_guard.CRITICAL_MEMORY_FLAGS 对齐：critical 级记忆 flag 红标（同 TracesPage）
const CRIT_MEMORY_FLAGS = new Set([
  'session_persist_failed',
  'long_term_load_corrupt',
  'long_term_save_failed',
]);

const LAYERS = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7'] as const;
const LAYER_LABEL: Record<string, string> = {
  L1: '基础设施',
  L2: 'LLM 依赖',
  L3: '请求性能',
  L4: 'Agent 决策',
  L5: '输出质量',
  L6: '前端体验',
  L7: '业务指标',
};

function healthTone(score: number): string {
  if (score >= 90) return 'text-green-600';
  if (score >= 70) return 'text-amber-500';
  return 'text-red-600';
}

export default function OverviewPage() {
  const { window } = useObsWindow();
  const navigate = useNavigate();
  const summary = usePolling<SummaryResponse>(() => getObsSummary(window), 60000, [window]);
  const events = usePolling<EventsResponse>(() => getObsEvents(8), 120000, []);
  const s = summary.data;

  if (summary.loading && !s) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-28" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  if (summary.error || !s || s.error) {
    return (
      <div className="p-6">
        <ErrorCard onRetry={summary.refresh} />
      </div>
    );
  }

  const fw = s.flywheel;
  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      {/* 健康分 + 飞轮四环节 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card title="健康分">
          <div className="flex items-baseline gap-1">
            <span className={`text-4xl font-bold tabular-nums ${healthTone(s.health_score)}`}>
              {s.health_score}
            </span>
            <span className="text-sm text-gray-400">/100</span>
          </div>
          <p className="mt-2 text-xs text-gray-400">
            窗口 {window} · {s.request_count ?? 0} 次请求
          </p>
        </Card>
        <Card title="待评审 BadCase">
          <div className="text-4xl font-bold tabular-nums text-gray-800">{fw?.badcase_pending ?? 0}</div>
          <button
            type="button"
            onClick={() => navigate('/observability/review')}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            前往评审台 →
          </button>
        </Card>
        <Card title="本周已合入">
          <div className="text-4xl font-bold tabular-nums text-green-600">{fw?.merged_this_week ?? 0}</div>
          <p className="mt-2 text-xs text-gray-400">回流用例进入评测集</p>
        </Card>
        <Card title="线上用例通过率">
          <div className="text-4xl font-bold tabular-nums text-gray-800">
            {fw?.prod_case_pass_rate == null ? '—' : `${Math.round(fw.prod_case_pass_rate * 100)}%`}
          </div>
          <p className="mt-2 text-xs text-gray-400">origin:production 追踪</p>
        </Card>
      </div>

      {/* 七层状态灯 */}
      <Card
        title="七层可观测状态灯"
        action={<span className="text-xs text-gray-400">点击卡片进入运行监控</span>}
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
          {LAYERS.map((k) => {
            const layer = s.layers?.[k];
            return (
              <button
                key={k}
                type="button"
                onClick={() => navigate('/observability/monitor')}
                className="rounded-lg border border-gray-200 p-3 text-left transition hover:border-blue-300 hover:bg-blue-50/40"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-400">{k}</span>
                  <StatusLight status={layer?.status} size="sm" />
                </div>
                <div className="mt-1 text-sm font-medium text-gray-700">{LAYER_LABEL[k]}</div>
                {layer?.note && <div className="mt-0.5 text-[10px] text-gray-400">{layer.note}</div>}
              </button>
            );
          })}
        </div>
      </Card>

      {/* 记忆健康（L4 明细：/summary layers.L4 记忆字段，与 MonitorPage 指标卡同源） */}
      <Card
        title="记忆健康"
        action={
          <StatusLight status={(s.layers?.L4?.memory_status as LayerStatus) ?? 'unknown'} size="sm" />
        }
      >
        {(() => {
          const l4 = s.layers?.L4 ?? {};
          const errs = (l4.memory_errors as number | undefined) ?? 0;
          const warns = (l4.memory_warns as number | undefined) ?? 0;
          const lt = (l4.long_term_storage as string | undefined) ?? 'unknown';
          const flags = Object.entries(
            (l4.memory_flag_dist as Record<string, number> | undefined) ?? {},
          );
          return (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div>
                <div className="text-xs text-gray-400">严重记忆异常</div>
                <div
                  className={`mt-1 text-lg font-semibold tabular-nums ${errs > 0 ? 'text-red-600' : 'text-green-600'}`}
                >
                  {errs}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">警告级记忆异常</div>
                <div
                  className={`mt-1 text-lg font-semibold tabular-nums ${warns > 0 ? 'text-amber-500' : 'text-gray-800'}`}
                >
                  {warns}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">长期存储探针</div>
                <div
                  className={`mt-1 text-lg font-semibold ${lt === 'critical' ? 'text-red-600' : lt === 'ok' ? 'text-green-600' : 'text-gray-800'}`}
                >
                  {lt}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">记忆 flag 分布</div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {flags.length === 0 ? (
                    <span className="text-xs text-gray-400">无异常</span>
                  ) : (
                    flags.map(([f, c]) => (
                      <Pill key={f} tone={CRIT_MEMORY_FLAGS.has(f) ? 'red' : 'amber'}>
                        {f}×{c}
                      </Pill>
                    ))
                  )}
                </div>
              </div>
            </div>
          );
        })()}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {/* 告警清单 */}
        <Card title={`告警（${s.alerts?.length ?? 0}）`}>
          {!s.alerts || s.alerts.length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-400">✅ 无未收敛告警</div>
          ) : (
            <ul className="space-y-2">
              {s.alerts.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <Pill tone={a.level === 'critical' ? 'red' : 'amber'}>
                    {a.layer} · {a.level}
                  </Pill>
                  <span className="text-gray-600">
                    <b className="text-gray-700">{a.rule}</b>：{a.msg}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* 最近变更事件 */}
        <Card title="最近变更" action={<span className="text-xs text-gray-400">{events.data?.count ?? 0}</span>}>
          {!events.data || events.data.items.length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-400">暂无变更事件</div>
          ) : (
            <ul className="space-y-2">
              {events.data.items.slice(0, 6).map((e, i) => (
                <li key={i} className="text-xs text-gray-600">
                  <span className="text-gray-400">{String(e.ts ?? '')}</span>
                  {' · '}
                  {String(e.type ?? e.event ?? e.kind ?? '变更')}
                  {e.message ? <span className="text-gray-500"> — {String(e.message)}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
