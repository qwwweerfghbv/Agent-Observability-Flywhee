// 视图⑥报告中心（SDD §5.10.1 / US-S1/S4/S6/S7）：pass_rate 趋势 + 运行列表 + 最新版本对比
// + flake 用例 + eval-trace live 抽屉（递归 setTimeout 轮询未完成 run，2s 刷新进度）。
// 数据源：GET /reports（聚合 list_eval_runs + auto_compare_latest + flake_cases.json）、
// GET /eval-traces/{run_id}?tail=true（span 树 + live 进度）。UI 一律经聚合 API 取数（D9/US-U3）。
import { useEffect, useState } from 'react';
import { getEvalTrace, getObsReports } from '../../lib/api';
import { usePolling } from '../../hooks/useObservability';
import { Card, EmptyCard, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import TrendChart, { type TrendMarker, type TrendPoint } from '../../components/observability/TrendChart';
import Drawer from '../../components/observability/Drawer';
import type { EvalSpan, EvalTraceResponse, FlakeCase, ReportsResponse } from '../../types/observability';

export default function ReportsPage() {
  const r = usePolling<ReportsResponse>(() => getObsReports(20), 60000, []);
  const [selRun, setSelRun] = useState<string | null>(null);

  if (r.loading && !r.data) {
    return (
      <div className="p-6">
        <Skeleton className="h-80" />
      </div>
    );
  }
  if (r.error || !r.data || r.data.error) {
    return (
      <div className="p-6">
        <ErrorCard onRetry={r.refresh} />
      </div>
    );
  }

  const d = r.data;
  const runs = d.runs ?? [];
  // 后端 runs 为降序（新→旧），趋势图需时序（旧→新）
  const chrono = [...runs].reverse();
  const points: TrendPoint[] = chrono.map((x) => ({
    label: (x.timestamp || x.run_id).slice(5, 16),
    value: typeof x.pass_rate === 'number' ? Math.round(x.pass_rate * 100) : null,
  }));
  // agent_version 变化点标竖线（"分数拐点 vs 版本变更"归因，US-S1）
  const markers: TrendMarker[] = [];
  chrono.forEach((x, i) => {
    if (i > 0 && x.agent_version && x.agent_version !== chrono[i - 1].agent_version) {
      markers.push({ index: i, label: x.agent_version.slice(0, 12) });
    }
  });
  const flakeCases: FlakeCase[] = d.flake?.flake_cases ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      {/* 通过率趋势 */}
      <Card
        title="通过率趋势"
        action={<span className="text-xs text-gray-400">{runs.length} 次运行 · 竖线=版本变更</span>}
      >
        {points.length === 0 ? (
          <EmptyCard
            title="暂无评测运行"
            hint="跑一次评测（python tests/eval/eval_runner.py）后此处出现 pass_rate 趋势"
          />
        ) : (
          <TrendChart points={points} markers={markers} unit="%" color="#16a34a" />
        )}
      </Card>

      {/* 最新版本对比（US-S1） */}
      {d.latest_comparison && <ComparisonCard comp={d.latest_comparison} />}

      <div className="grid gap-4 lg:grid-cols-3">
        {/* 运行列表 */}
        <div className="lg:col-span-2">
          <Card className="overflow-hidden p-0" title="评测运行（点击查看链路）">
            {runs.length === 0 ? (
              <EmptyCard title="暂无运行记录" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 text-left text-xs text-gray-400">
                    <tr>
                      <th className="px-4 py-2">run_id</th>
                      <th className="px-4 py-2">时间</th>
                      <th className="px-4 py-2">版本</th>
                      <th className="px-4 py-2 text-right">用例</th>
                      <th className="px-4 py-2 text-right">通过率</th>
                      <th className="px-4 py-2">门禁</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((x) => (
                      <tr
                        key={x.run_id}
                        onClick={() => setSelRun(x.run_id)}
                        className="cursor-pointer border-t border-gray-100 hover:bg-blue-50/40"
                      >
                        <td className="px-4 py-2 font-mono text-xs text-gray-600">{x.run_id}</td>
                        <td className="whitespace-nowrap px-4 py-2 text-xs text-gray-400">
                          {x.timestamp || '—'}
                        </td>
                        <td className="px-4 py-2 text-xs text-gray-600">{x.agent_version || '—'}</td>
                        <td className="px-4 py-2 text-right text-xs tabular-nums text-gray-700">
                          {x.total_cases}
                        </td>
                        <td className="px-4 py-2 text-right text-xs tabular-nums">
                          <span
                            className={
                              x.pass_rate >= 0.8
                                ? 'text-green-600'
                                : x.pass_rate >= 0.6
                                  ? 'text-amber-600'
                                  : 'text-red-600'
                            }
                          >
                            {(x.pass_rate * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <Pill tone={x.gate_passed ? 'green' : 'red'}>
                            {x.gate_passed ? '通过' : '未过'}
                          </Pill>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        {/* flake 用例（US-S4：不参与门禁） */}
        <div>
          <Card className="h-full" title={`Flake 用例（${flakeCases.length}）`}>
            {flakeCases.length === 0 ? (
              <EmptyCard
                title="无 flake 用例"
                hint="连续多次运行结果稳定；不稳定用例会被识别为 flake 并排除出门禁（US-S4）"
              />
            ) : (
              <ul className="space-y-2">
                {flakeCases.map((f) => (
                  <li key={f.case_id} className="rounded-lg border border-gray-100 px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-xs text-gray-700" title={f.case_id}>
                        {f.case_id}
                      </span>
                      <Pill tone={f.pass_rate < 0.5 ? 'red' : 'amber'}>
                        {(f.pass_rate * 100).toFixed(0)}%
                      </Pill>
                    </div>
                    <div className="mt-0.5 text-[11px] text-gray-400">
                      {f.pass_count}/{f.runs} 次通过
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* eval-trace live 抽屉（US-S6/S7） */}
      <Drawer
        open={!!selRun}
        onClose={() => setSelRun(null)}
        title={`评测链路 ${selRun ?? ''}`}
        width="max-w-2xl"
      >
        {selRun && <EvalTraceLive runId={selRun} />}
      </Drawer>
    </div>
  );
}

/** 最新版本对比卡：回归告警高亮 + 其余字段泛化 KV 渲染 */
function ComparisonCard({ comp }: { comp: Record<string, unknown> }) {
  const regression = Boolean(comp.regression_alert || comp.is_regression);
  const compared = comp.compared !== false && comp.error == null;
  return (
    <Card
      title="最新版本对比"
      action={
        regression ? (
          <Pill tone="red">⚠️ 回归告警</Pill>
        ) : compared ? (
          <Pill tone="green">无回归</Pill>
        ) : (
          <Pill tone="gray">未对比</Pill>
        )
      }
    >
      {!compared ? (
        <p className="text-xs text-gray-400">{String(comp.reason ?? comp.error ?? '无历史版本可对比')}</p>
      ) : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 md:grid-cols-3">
          {Object.entries(comp)
            .filter(([k]) => k !== 'compared' && k !== 'regression_alert')
            .map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between gap-2 border-b border-gray-50 py-0.5 text-xs"
              >
                <span className="shrink-0 text-gray-400">{k}</span>
                <span className="truncate font-mono text-gray-700" title={fmtVal(v)}>
                  {fmtVal(v)}
                </span>
              </div>
            ))}
        </div>
      )}
    </Card>
  );
}

/** 评测链路 live：递归 setTimeout 轮询未完成 run（progress.live），卸载即停 */
function EvalTraceLive({ runId }: { runId: string }) {
  const [data, setData] = useState<EvalTraceResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      const res = await getEvalTrace(runId, true);
      if (!alive) return;
      setData(res);
      setLoading(false);
      // 仍在跑（未落 eval_run phase=end）→ 2s 后再取，实现 live 进度（US-S7）
      if (res && !res.error && res.progress?.live) {
        timer = setTimeout(load, 2000);
      }
    };
    void load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [runId]);

  if (loading) return <Skeleton className="h-64" />;
  if (!data || data.error) {
    return (
      <EmptyCard
        title="无法加载评测链路"
        hint={data?.error ?? '该 run 没有 trace 记录（需 M5 之后跑的评测才有 eval_traces）'}
      />
    );
  }

  const p = data.progress;
  const pct = p.total > 0 ? Math.round((p.done / p.total) * 100) : 0;
  const spans = data.spans ?? [];
  const cases = spans.filter((s) => s.span === 'case');
  // case 为顶层（parent=RUN），service_call/judge_call 以 case.span_id 为 parent
  const subspansOf = (id?: string | null) =>
    spans.filter((s) => s.span !== 'case' && s.parent != null && s.parent === id);
  const er = data.eval_run ?? {};

  return (
    <div className="space-y-4">
      {/* live 进度条 */}
      <div>
        <div className="mb-1 flex items-center justify-between text-xs text-gray-500">
          <span>
            进度 {p.done}/{p.total}
            {p.current ? ` · 当前 ${String(p.current).slice(0, 16)}` : ''}
          </span>
          {p.live ? <Pill tone="amber">● 运行中（2s 自动刷新）</Pill> : <Pill tone="green">已完成</Pill>}
        </div>
        <div className="h-2 overflow-hidden rounded bg-gray-100">
          <div
            className={`h-2 rounded ${p.live ? 'bg-amber-400' : 'bg-green-500'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* 运行摘要（eval_run span attrs） */}
      <Card title="运行摘要">
        {Object.keys(er).length === 0 ? (
          <div className="py-3 text-center text-xs text-gray-400">无 eval_run 摘要</div>
        ) : (
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {Object.entries(er).map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between gap-2 border-b border-gray-50 py-0.5 text-xs"
              >
                <span className="shrink-0 text-gray-400">{k}</span>
                <span className="truncate font-mono text-gray-700" title={fmtVal(v)}>
                  {k === 'pass_rate' && typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : fmtVal(v)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* span 树 */}
      <Card title={`Span 树（${cases.length} 用例 · ${spans.length} span）`}>
        {cases.length === 0 ? (
          <div className="py-4 text-center text-xs text-gray-400">
            {spans.length === 0 ? '暂无 span 记录' : `${spans.length} 个 span（尚无 case 分组）`}
          </div>
        ) : (
          <ul className="space-y-2">
            {cases.map((c, ci) => (
              <CaseNode key={c.span_id ?? ci} span={c} subspans={subspansOf(c.span_id)} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/** 单用例节点：状态徽章 + 得分/耗时 + 子 span（service_call/judge_call）明细 */
function CaseNode({ span, subspans }: { span: EvalSpan; subspans: EvalSpan[] }) {
  const a = span.attrs ?? {};
  const passed = a.passed === true;
  const status = String(a.status ?? '');
  const tone: 'green' | 'red' | 'amber' | 'gray' = passed
    ? 'green'
    : status === 'skipped'
      ? 'gray'
      : status === 'error'
        ? 'red'
        : 'amber';
  const score = typeof a.weighted_score === 'number' ? a.weighted_score.toFixed(2) : null;
  const dur = typeof a.duration_ms === 'number' ? Math.round(a.duration_ms) : null;
  return (
    <li className="rounded-lg border border-gray-100 p-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Pill tone={tone}>{passed ? '✓ 通过' : status || '未过'}</Pill>
        <span className="font-mono text-gray-700">{span.span_id ?? '—'}</span>
        {a.module != null && <span className="text-gray-400">{String(a.module)}</span>}
        <span className="ml-auto tabular-nums text-gray-500">
          {score ? `得分 ${score}` : ''}
          {dur != null ? ` · ${dur}ms` : ''}
        </span>
      </div>
      {subspans.length > 0 && (
        <ul className="mt-1 space-y-0.5 border-l border-gray-100 pl-3">
          {subspans.map((s, i) => {
            const sa = s.attrs ?? {};
            return (
              <li key={i} className="text-[11px] text-gray-500">
                <span className="font-mono text-gray-400">{s.span}</span>
                {s.span === 'service_call' && (
                  <>
                    {' · '}
                    {String(sa.service_name ?? '')} {Math.round(Number(sa.duration_ms ?? 0))}ms
                    {sa.degraded ? ' · 降级' : ''}
                  </>
                )}
                {s.span === 'judge_call' && (
                  <>
                    {' · '}
                    {String(sa.judge_type ?? '')} score={fmtVal(sa.score)}
                    {sa.red_line ? ' · 红线' : ''}
                  </>
                )}
                {s.span !== 'service_call' && s.span !== 'judge_call' && (
                  <> · {summarize(sa)}</>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

/** unknown 值安全格式化 */
function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3);
  if (typeof v === 'string') return v || '—';
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

/** attrs 摘要（前 3 个键值，泛化 span 用） */
function summarize(attrs: Record<string, unknown>): string {
  const parts = Object.entries(attrs)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${fmtVal(v)}`);
  return parts.join(' ') || '—';
}
