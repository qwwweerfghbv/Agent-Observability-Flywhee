// 视图③链路查询（SDD §5.10.1 / US-O3）：/traces 列表 + 过滤，点击行开 Drawer 看
// 单链路耗时分解（Waterfall）+ delta 节奏（GapBars）+ 意图/LLM/质量/版本/关联日志。
import { useEffect, useState } from 'react';
import { getTraceDetail, listTraces } from '../../lib/api';
import { useObsWindow, usePolling } from '../../hooks/useObservability';
import { Card, EmptyCard, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import Drawer from '../../components/observability/Drawer';
import Waterfall, { type WaterfallSegment } from '../../components/observability/Waterfall';
import GapBars from '../../components/observability/GapBars';
import type { TraceDetail, TraceListItem } from '../../types/observability';

type ListResp = { count: number; returned: number; items: TraceListItem[] };

const STATUS_TONE: Record<string, 'gray' | 'green' | 'amber' | 'red' | 'blue'> = {
  ok: 'green',
  error: 'red',
  interrupted: 'amber',
  timeout: 'red',
};

// 与后端 memory_guard.CRITICAL_MEMORY_FLAGS 对齐：critical 级记忆 flag 红标
const CRIT_MEMORY_FLAGS = new Set([
  'session_persist_failed',
  'long_term_load_corrupt',
  'long_term_save_failed',
]);

function statusTone(s: string): 'gray' | 'green' | 'amber' | 'red' | 'blue' {
  return STATUS_TONE[s] ?? 'gray';
}

export default function TracesPage() {
  const { window } = useObsWindow();
  const [status, setStatus] = useState('');
  const [level, setLevel] = useState('');
  const [sel, setSel] = useState<string | null>(null);

  const list = usePolling<ListResp>(
    () =>
      listTraces({
        window,
        status: status || undefined,
        level: level || undefined,
        limit: 50,
      }),
    30000,
    [window, status, level],
  );

  // Drawer 详情：选中 trace 后单独取（不走 usePolling，避免 null=error 语义）
  const [detail, setDetail] = useState<TraceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  useEffect(() => {
    if (!sel) {
      setDetail(null);
      return;
    }
    let alive = true;
    setDetailLoading(true);
    void getTraceDetail(sel).then((d) => {
      if (!alive) return;
      setDetail(d);
      setDetailLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [sel]);

  const items = list.data?.items ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      {/* 过滤条 */}
      <Card>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-1.5 text-xs text-gray-500">
            状态
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-lg border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">全部</option>
              <option value="ok">ok</option>
              <option value="error">error</option>
              <option value="interrupted">interrupted</option>
              <option value="timeout">timeout</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-gray-500">
            <input
              type="checkbox"
              checked={level === 'critical'}
              onChange={(e) => setLevel(e.target.checked ? 'critical' : '')}
              className="rounded border-gray-300"
            />
            仅看严重（错误/安全命中）
          </label>
          <button
            type="button"
            onClick={list.refresh}
            className="ml-auto rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            ↻ 刷新
          </button>
          <span className="text-xs text-gray-400">
            命中 {list.data?.count ?? 0} · 显示 {items.length}
          </span>
        </div>
      </Card>

      {/* 链路列表 */}
      {list.loading && !list.data ? (
        <Skeleton className="h-72" />
      ) : list.error || !list.data ? (
        <ErrorCard onRetry={list.refresh} />
      ) : items.length === 0 ? (
        <EmptyCard title="窗口内暂无链路" hint="调整时间窗或过滤条件，或发送一条聊天消息后再看" />
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-400">
                <tr>
                  <th className="px-4 py-2">时间</th>
                  <th className="px-4 py-2">路径</th>
                  <th className="px-4 py-2">意图</th>
                  <th className="px-4 py-2">状态</th>
                  <th className="px-4 py-2 text-right">时长</th>
                  <th className="px-4 py-2 text-right">TTFT</th>
                  <th className="px-4 py-2">标记</th>
                </tr>
              </thead>
              <tbody>
                {items.map((t) => (
                  <tr
                    key={t.trace_id}
                    onClick={() => setSel(t.trace_id)}
                    className="cursor-pointer border-t border-gray-100 hover:bg-blue-50/40"
                  >
                    <td className="whitespace-nowrap px-4 py-2 text-xs text-gray-400">{t.ts}</td>
                    <td className="px-4 py-2 text-xs text-gray-600">{t.path}</td>
                    <td className="px-4 py-2 text-xs text-gray-600">{t.intent ?? '—'}</td>
                    <td className="px-4 py-2">
                      <Pill tone={statusTone(t.status)}>{t.status}</Pill>
                    </td>
                    <td className="px-4 py-2 text-right text-xs tabular-nums text-gray-700">
                      {t.duration_ms != null ? `${Math.round(t.duration_ms)}ms` : '—'}
                    </td>
                    <td className="px-4 py-2 text-right text-xs tabular-nums text-gray-700">
                      {t.ttft_ms != null ? `${Math.round(t.ttft_ms)}ms` : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex gap-1">
                        {t.degraded && <Pill tone="amber">降级</Pill>}
                        {t.user_interrupted && <Pill tone="gray">中断</Pill>}
                        {t.security_hit && <Pill tone="red">安全</Pill>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* 详情抽屉 */}
      <Drawer open={!!sel} onClose={() => setSel(null)} title={`链路详情 ${sel ?? ''}`} width="max-w-2xl">
        {detailLoading ? (
          <Skeleton className="h-64" />
        ) : !detail || detail.error ? (
          <EmptyCard title="无法加载链路详情" hint={detail?.error ?? '该 trace 可能已轮转归档'} />
        ) : (
          <TraceDetailView d={detail} />
        )}
      </Drawer>
    </div>
  );
}

function TraceDetailView({ d }: { d: TraceDetail }) {
  const t = d.timing;
  const tail =
    t.total_ms != null && t.ttft_ms != null && t.stream_span_ms != null
      ? Math.max(0, Math.round(t.total_ms - t.ttft_ms - t.stream_span_ms))
      : null;
  const segments: WaterfallSegment[] = [
    { label: '首字前', value: t.ttft_ms != null ? Math.round(t.ttft_ms) : null, color: 'bg-indigo-500' },
    { label: '流式输出', value: t.stream_span_ms != null ? Math.round(t.stream_span_ms) : null, color: 'bg-blue-500' },
    { label: '收尾', value: tail, color: 'bg-gray-400' },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <Pill tone={statusTone(d.status)}>{d.status}</Pill>
        <span>{d.method}</span>
        <span>{d.path}</span>
        <span className="text-gray-400">{d.ts}</span>
      </div>

      <section>
        <h3 className="mb-2 text-xs font-semibold text-gray-500">耗时分解</h3>
        <Waterfall segments={segments} />
        <p className="mt-2 text-[11px] text-gray-400">
          总时长 {t.total_ms != null ? `${Math.round(t.total_ms)}ms` : '—'} · 前置处理{' '}
          {t.preprocess_ms != null ? `${Math.round(t.preprocess_ms)}ms` : '—'} · LLM{' '}
          {t.llm_duration_ms != null ? `${Math.round(t.llm_duration_ms)}ms` : '—'}
        </p>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold text-gray-500">
          delta 节奏（{d.stream.delta_count ?? 0} 个增量 · 间隔中位{' '}
          {d.stream.gap_median_ms != null ? `${Math.round(d.stream.gap_median_ms)}ms` : '—'}）
        </h3>
        <GapBars gaps={d.stream.delta_gaps ?? []} />
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <section>
          <h3 className="mb-2 text-xs font-semibold text-gray-500">意图</h3>
          <KV k="意图" v={d.intent.name ?? '—'} />
          <KV k="置信度" v={d.intent.confidence != null ? d.intent.confidence.toFixed(2) : '—'} />
          <KV k="歧义" v={d.intent.ambiguous ? '是' : '否'} />
        </section>
        <section>
          <h3 className="mb-2 text-xs font-semibold text-gray-500">LLM</h3>
          <KV k="模型" v={d.llm.model ?? '—'} />
          <KV
            k="tokens"
            v={
              d.llm.tokens
                ? `${d.llm.tokens.prompt}+${d.llm.tokens.completion}=${d.llm.tokens.total}`
                : '—'
            }
          />
          <KV k="降级" v={d.llm.degraded ? '是' : '否'} />
          {d.llm.llm_error && <KV k="错误" v={d.llm.llm_error} />}
        </section>
        <section>
          <h3 className="mb-2 text-xs font-semibold text-gray-500">质量</h3>
          <KV k="卡片数" v={String(d.quality.card_count ?? '—')} />
          <KV k="空回复" v={d.quality.empty_reply ? '是' : '否'} />
          <KV k="安全命中" v={d.quality.security_hit ? '是' : '否'} />
          {d.quality.quality_flags && d.quality.quality_flags.length > 0 && (
            <KV k="标志" v={d.quality.quality_flags.join(', ')} />
          )}
          {d.quality.scores ? (
            <>
              <KV k="切题" v={String(d.quality.scores.relevance ?? '—')} />
              <KV k="回复质量" v={String(d.quality.scores.quality ?? '—')} />
              <KV k="安全分" v={String(d.quality.scores.red_line ?? '—')} />
              <KV k="真实性" v={String(d.quality.scores.truthfulness ?? '—')} />
              <KV k="综合" v={String(d.quality.scores.overall ?? '—')} />
              {d.quality.judge_reason && (
                <p className="mt-1 whitespace-normal text-[11px] leading-4 text-gray-500">
                  评语：{d.quality.judge_reason}
                </p>
              )}
            </>
          ) : (
            <p className="mt-1 text-[11px] text-gray-400">未评分（未命中抽样或评分进行中）</p>
          )}
        </section>
        <section>
          <h3 className="mb-2 text-xs font-semibold text-gray-500">版本</h3>
          {d.version ? (
            Object.entries(d.version).map(([k, v]) => <KV key={k} k={k} v={String(v)} />)
          ) : (
            <KV k="版本" v="—" />
          )}
        </section>
        <section>
          <h3 className="mb-2 text-xs font-semibold text-gray-500">记忆</h3>
          <KV
            k="消息持久化"
            v={d.memory?.msg_persisted == null ? '—' : d.memory.msg_persisted ? '是' : '否（失败）'}
          />
          {d.memory?.flags && d.memory.flags.length > 0 ? (
            <div className="mt-1 flex flex-wrap gap-1">
              {d.memory.flags.map((f) => (
                <Pill key={f} tone={CRIT_MEMORY_FLAGS.has(f) ? 'red' : 'amber'}>
                  {f}
                </Pill>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-gray-400">无记忆异常 flag</p>
          )}
          {d.memory?.spans && d.memory.spans.length > 0 && (
            <ul className="mt-1 space-y-0.5">
              {d.memory.spans.map((sp, i) => (
                <li key={i} className="text-[11px] text-gray-500">
                  {String(sp.op)} · {String(sp.memory_type)} · success={String(sp.success)}
                  {sp.trimmed != null ? ` · trimmed=${String(sp.trimmed)}` : ''}
                  {sp.error ? ` · ${String(sp.error)}` : ''}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section>
        <h3 className="mb-2 text-xs font-semibold text-gray-500">关联日志 / span（{d.logs.length}）</h3>
        {d.logs.length === 0 ? (
          <div className="py-3 text-center text-xs text-gray-400">无 span 记录</div>
        ) : (
          <pre className="max-h-64 overflow-auto rounded-lg bg-gray-900 p-3 text-[11px] leading-5 text-gray-100">
            {d.logs.join('\n')}
          </pre>
        )}
      </section>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2 py-0.5 text-xs">
      <span className="shrink-0 text-gray-400">{k}</span>
      <span className="truncate text-right text-gray-700" title={v}>
        {v}
      </span>
    </div>
  );
}
