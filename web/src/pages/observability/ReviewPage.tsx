// 视图⑤评审台（SDD §5.10.1/§5.10.6 / US-B3）：双栏 + 键盘流（J/K 上下、M 合入、D 丢弃）。
// 数据源：GET /badcases + POST /badcases/{id}/review。合入需 expected，丢弃需 reason。
// 输入框聚焦期间挂起键盘监听防误触；操作成功后刷新队列。
import { useCallback, useEffect, useRef, useState } from 'react';
import { listBadCases, reviewBadCase } from '../../lib/api';
import { usePolling } from '../../hooks/useObservability';
import { Card, EmptyCard, ErrorCard, Pill, Skeleton } from '../../components/observability/common';
import type { BadCaseDraft, BadCaseListResponse } from '../../types/observability';

const SEV_TONE: Record<string, 'red' | 'amber' | 'blue' | 'gray'> = {
  critical: 'red',
  high: 'amber',
  medium: 'blue',
  low: 'gray',
};

export default function ReviewPage() {
  const [status, setStatus] = useState<'pending' | 'processed'>('pending');
  // 评审为交互态，不自动轮询（intervalMs=0）；切状态或手动刷新时重取
  const list = usePolling<BadCaseListResponse>(() => listBadCases(status, false), 0, [status]);
  const items: BadCaseDraft[] = list.data?.items ?? [];

  const [idx, setIdx] = useState(0);
  const [expected, setExpected] = useState('');
  const [reason, setReason] = useState('');
  const [discarding, setDiscarding] = useState(false);
  const [busy, setBusy] = useState(false);
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  const sel = items[idx] ?? null;
  const selId = sel?.id;

  // 选中项变化 → 预填 expected，重置丢弃态
  useEffect(() => {
    setExpected(sel?.draft?.expected ?? '');
    setReason('');
    setDiscarding(false);
  }, [selId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 列表刷新后夹取 idx
  useEffect(() => {
    if (idx > items.length - 1) setIdx(Math.max(0, items.length - 1));
  }, [items.length, idx]);

  const doMerge = useCallback(async () => {
    if (!sel || !expected.trim() || busy) return;
    setBusy(true);
    await reviewBadCase(sel.id, 'merge', expected.trim(), '');
    setBusy(false);
    list.refresh();
  }, [sel, expected, busy, list]);

  const doDiscard = useCallback(async () => {
    if (!sel || !reason.trim() || busy) return;
    setBusy(true);
    await reviewBadCase(sel.id, 'discard', '', reason.trim());
    setBusy(false);
    setDiscarding(false);
    list.refresh();
  }, [sel, reason, busy, list]);

  // 键盘流
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
      const k = e.key.toLowerCase();
      if (k === 'j') {
        e.preventDefault();
        setIdx((i) => Math.min(items.length - 1, i + 1));
      } else if (k === 'k') {
        e.preventDefault();
        setIdx((i) => Math.max(0, i - 1));
      } else if (k === 'm') {
        e.preventDefault();
        if (expected.trim()) void doMerge();
      } else if (k === 'd') {
        e.preventDefault();
        setDiscarding(true);
        setTimeout(() => reasonRef.current?.focus(), 0);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [items.length, expected, doMerge]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
      {/* 工具条 */}
      <Card>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <div className="flex items-center gap-0.5 rounded-lg bg-gray-100 p-0.5">
            {(['pending', 'processed'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  setStatus(s);
                  setIdx(0);
                }}
                className={`rounded-md px-3 py-1 text-xs ${
                  status === s ? 'bg-white font-medium text-blue-700 shadow-sm' : 'text-gray-500'
                }`}
              >
                {s === 'pending' ? '待评审' : '已处理'}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={list.refresh}
            className="rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            ↻ 刷新
          </button>
          <span className="text-xs text-gray-400">
            {items.length} 条 · 键盘 <Kbd>J</Kbd>/<Kbd>K</Kbd> 切换 <Kbd>M</Kbd> 合入 <Kbd>D</Kbd> 丢弃
          </span>
          {list.data?.by_severity && (
            <span className="ml-auto flex gap-1">
              {Object.entries(list.data.by_severity).map(([k, v]) => (
                <Pill key={k} tone={SEV_TONE[k] ?? 'gray'}>
                  {k} {v}
                </Pill>
              ))}
            </span>
          )}
        </div>
      </Card>

      {list.loading && !list.data ? (
        <Skeleton className="h-80" />
      ) : list.error || !list.data ? (
        <ErrorCard onRetry={list.refresh} />
      ) : items.length === 0 ? (
        <EmptyCard
          title={status === 'pending' ? '🎉 评审队列已清空' : '暂无已处理记录'}
          hint="线上回流的 bad case 会按 severity 排序出现在此，人工确认后才合入评测集（D7）"
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-5">
          {/* 左：队列 */}
          <div className="md:col-span-2">
            <Card className="h-full p-0" title={`队列（${items.length}）`}>
              <ul className="max-h-[70vh] overflow-y-auto p-2">
                {items.map((it, i) => (
                  <li key={it.id}>
                    <button
                      type="button"
                      onClick={() => setIdx(i)}
                      className={`w-full rounded-lg px-3 py-2 text-left transition ${
                        i === idx ? 'bg-blue-50 ring-1 ring-blue-200' : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Pill tone={SEV_TONE[it.severity] ?? 'gray'}>{it.severity}</Pill>
                        <span className="truncate text-xs font-medium text-gray-700">{it.rule}</span>
                        {it.occurrences && it.occurrences > 1 && (
                          <span className="ml-auto text-[10px] text-gray-400">×{it.occurrences}</span>
                        )}
                      </div>
                      <div className="mt-1 truncate text-xs text-gray-500">{it.message_preview || it.draft?.input || '—'}</div>
                      <div className="mt-0.5 text-[10px] text-gray-400">
                        {it.layer} · {it.ts}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          {/* 右：详情 + 作业 */}
          <div className="md:col-span-3">
            {sel ? (
              <DraftPanel
                sel={sel}
                expected={expected}
                setExpected={setExpected}
                reason={reason}
                setReason={setReason}
                discarding={discarding}
                setDiscarding={setDiscarding}
                busy={busy}
                reasonRef={reasonRef}
                onMerge={() => void doMerge()}
                onDiscard={() => void doDiscard()}
              />
            ) : (
              <EmptyCard title="未选中草稿" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-gray-300 bg-gray-50 px-1 py-0.5 font-mono text-[10px] text-gray-600">
      {children}
    </kbd>
  );
}

function DraftPanel({
  sel,
  expected,
  setExpected,
  reason,
  setReason,
  discarding,
  setDiscarding,
  busy,
  reasonRef,
  onMerge,
  onDiscard,
}: {
  sel: BadCaseDraft;
  expected: string;
  setExpected: (v: string) => void;
  reason: string;
  setReason: (v: string) => void;
  discarding: boolean;
  setDiscarding: (v: boolean) => void;
  busy: boolean;
  reasonRef: React.RefObject<HTMLTextAreaElement | null>;
  onMerge: () => void;
  onDiscard: () => void;
}) {
  const m = sel.metrics ?? {};
  const d = sel.draft ?? ({} as BadCaseDraft['draft']);
  const canMerge = expected.trim().length > 0 && !busy;
  const canDiscard = reason.trim().length > 0 && !busy;
  return (
    <Card title={<span>草稿详情 · <span className="font-mono text-xs text-gray-400">{sel.id}</span></span>}>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-2">
          <Pill tone={SEV_TONE[sel.severity] ?? 'gray'}>{sel.severity}</Pill>
          <Pill tone="blue">{sel.rule}</Pill>
          <Pill tone="gray">{sel.layer}</Pill>
          <span className="text-xs text-gray-400">trace {sel.trace_id}</span>
        </div>

        {sel.pii_hits && sel.pii_hits.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            ⚠️ 脱敏扫描命中 {sel.pii_hits.length} 处（{sel.pii_hits.join(', ')}），合入前请二次确认
          </div>
        )}

        <Field label="原始消息">
          <p className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700">
            {sel.message_preview || '—'}
          </p>
        </Field>

        <Field label="指标">
          <div className="flex gap-3 text-xs text-gray-500">
            <span>时长 {m.duration_ms != null ? `${Math.round(m.duration_ms)}ms` : '—'}</span>
            <span>TTFT {m.ttft_ms != null ? `${Math.round(m.ttft_ms)}ms` : '—'}</span>
            <span>gap 中位 {m.gap_median_ms != null ? `${Math.round(m.gap_median_ms)}ms` : '—'}</span>
          </div>
        </Field>

        <Field label="预填 EvalCase">
          <div className="space-y-1 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600">
            <div>module：<b>{d.module ?? '—'}</b> · priority：<b>{d.priority ?? '—'}</b></div>
            <div>tags：{(d.tags ?? []).join(', ') || '—'}</div>
            <div className="truncate">input：{d.input ?? '—'}</div>
          </div>
        </Field>

        {/* 合入：expected 必填 */}
        <Field label="期望行为（合入必填，D7 人工判断）">
          <textarea
            value={expected}
            onChange={(e) => setExpected(e.target.value)}
            rows={3}
            placeholder="描述该输入应有的正确行为，作为回归用例的 expected"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </Field>

        {/* 丢弃：reason 必填 */}
        {discarding && (
          <Field label="丢弃原因（必填，留痕）">
            <textarea
              ref={reasonRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder="为何该草稿无需合入（如误报/重复/无价值）"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-red-400"
            />
          </Field>
        )}

        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={onMerge}
            disabled={!canMerge}
            className="rounded-lg bg-green-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-40"
          >
            ✓ 合入评测集 (M)
          </button>
          {discarding ? (
            <>
              <button
                type="button"
                onClick={onDiscard}
                disabled={!canDiscard}
                className="rounded-lg bg-red-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40"
              >
                🗑 确认丢弃
              </button>
              <button
                type="button"
                onClick={() => setDiscarding(false)}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setDiscarding(true)}
              disabled={busy}
              className="rounded-lg border border-gray-300 px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40"
            >
              ✕ 丢弃 (D)
            </button>
          )}
          {!expected.trim() && !discarding && (
            <span className="text-xs text-gray-400">填写期望行为后可合入</span>
          )}
        </div>
      </div>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-gray-500">{label}</div>
      {children}
    </div>
  );
}
