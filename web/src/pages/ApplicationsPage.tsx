import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  createApplication,
  deleteApplication,
  getApplicationStats,
  listApplications,
  listJobs,
  updateApplication,
} from '../lib/api';
import type {
  ApplicationRecord,
  ApplicationStats,
  ApplicationStatus,
  JobSummary,
} from '../types/models';

/** 状态 → 中文标签 + 徽章配色 */
const STATUS_META: Record<ApplicationStatus, { label: string; badge: string }> = {
  pending: { label: '待投递', badge: 'bg-gray-100 text-gray-600' },
  applied: { label: '已投递', badge: 'bg-blue-100 text-blue-700' },
  screening: { label: '筛选中', badge: 'bg-purple-100 text-purple-700' },
  interview: { label: '面试中', badge: 'bg-amber-100 text-amber-700' },
  offer: { label: 'Offer', badge: 'bg-green-100 text-green-700' },
  rejected: { label: '被拒', badge: 'bg-red-100 text-red-600' },
  inappropriate: { label: '不合适', badge: 'bg-gray-100 text-gray-400' },
};
const ALL_STATUSES = Object.keys(STATUS_META) as ApplicationStatus[];

/**
 * 投递追踪页（P3）：
 * - 顶部统计六格（GET /api/application/stats）
 * - 新建投递（岗位下拉来自岗位库 + 平台 + 状态 + 备注）
 * - 状态筛选 + 行内状态直改（PUT）+ 删除
 */
export default function ApplicationsPage() {
  const [apps, setApps] = useState<ApplicationRecord[]>([]);
  const [stats, setStats] = useState<ApplicationStats | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<ApplicationStatus | 'all'>('all');
  const [showForm, setShowForm] = useState(false);

  // 新建表单
  const [fJobId, setFJobId] = useState<number | ''>('');
  const [fPlatform, setFPlatform] = useState('Boss');
  const [fStatus, setFStatus] = useState<ApplicationStatus>('applied');
  const [fNotes, setFNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const [list, st, jl] = await Promise.all([
      listApplications(undefined, 100),
      getApplicationStats(),
      listJobs(100),
    ]);
    setApps(list ?? []);
    setStats(st);
    setJobs(jl?.jobs ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const jobTitle = (jobId: number) => {
    const j = jobs.find((x) => x.id === jobId);
    return j ? `${j.title} @ ${j.company}` : `岗位#${jobId}`;
  };

  const submit = async () => {
    if (fJobId === '' || submitting) return;
    setSubmitting(true);
    const resp = await createApplication({
      job_id: fJobId,
      platform: fPlatform,
      status: fStatus,
      notes: fNotes,
    });
    setSubmitting(false);
    if (resp) {
      setShowForm(false);
      setFJobId('');
      setFNotes('');
      void refresh();
    }
  };

  const changeStatus = async (id: number, status: ApplicationStatus) => {
    setApps((prev) => prev.map((a) => (a.id === id ? { ...a, status } : a)));
    const resp = await updateApplication(id, { status });
    if (!resp) void refresh(); // 失败回滚
  };

  const remove = async (id: number) => {
    if (!window.confirm('确定删除该投递记录？')) return;
    const ok = await deleteApplication(id);
    if (ok) {
      setApps((prev) => prev.filter((a) => a.id !== id));
      void getApplicationStats().then(setStats);
    }
  };

  const filtered = filter === 'all' ? apps : apps.filter((a) => a.status === filter);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">📋 投递追踪</h1>
            <p className="mt-1 text-sm text-gray-500">记录每一次投递，跟踪状态直到 Offer</p>
          </div>
          <button
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-40"
            disabled={jobs.length === 0}
            title={jobs.length === 0 ? '请先在岗位管理页录入岗位' : ''}
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? '收起' : '➕ 新建投递'}
          </button>
        </div>

        {/* 统计六格 */}
        <div className="mt-5 grid grid-cols-3 gap-3 md:grid-cols-6">
          <StatCell label="今日" value={stats?.today_count ?? '-'} tone="text-blue-600" />
          <StatCell label="本周" value={stats?.week_count ?? '-'} tone="text-gray-800" />
          <StatCell label="累计" value={stats?.total_applied ?? '-'} tone="text-gray-800" />
          <StatCell label="面试" value={stats?.interview_count ?? '-'} tone="text-amber-600" />
          <StatCell label="Offer" value={stats?.offer_count ?? '-'} tone="text-green-600" />
          <StatCell
            label="通过率"
            value={stats ? `${Math.round(stats.pass_rate * 100)}%` : '-'}
            tone="text-purple-600"
          />
        </div>

        {/* 新建表单 */}
        {showForm && (
          <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm">
                <span className="mb-1 block text-xs text-gray-500">岗位（来自岗位库）</span>
                <select
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={fJobId}
                  onChange={(e) => setFJobId(e.target.value === '' ? '' : Number(e.target.value))}
                >
                  <option value="">选择岗位...</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title} @ {j.company}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-xs text-gray-500">平台</span>
                <select
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={fPlatform}
                  onChange={(e) => setFPlatform(e.target.value)}
                >
                  {['Boss', '猎聘', '拉勾', '内推', '官网', '其他'].map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-xs text-gray-500">状态</span>
                <select
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={fStatus}
                  onChange={(e) => setFStatus(e.target.value as ApplicationStatus)}
                >
                  {ALL_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-xs text-gray-500">备注</span>
                <input
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="如：内推人姓名 / 面试轮次"
                  value={fNotes}
                  onChange={(e) => setFNotes(e.target.value)}
                />
              </label>
            </div>
            <div className="mt-3 flex justify-end">
              <button
                className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-40"
                disabled={fJobId === '' || submitting}
                onClick={submit}
              >
                {submitting ? '提交中...' : '创建投递记录'}
              </button>
            </div>
          </div>
        )}

        {/* 状态筛选 */}
        <div className="mt-5 flex flex-wrap gap-1.5">
          <FilterChip active={filter === 'all'} onClick={() => setFilter('all')}>
            全部 {apps.length}
          </FilterChip>
          {ALL_STATUSES.map((s) => {
            const n = apps.filter((a) => a.status === s).length;
            return (
              <FilterChip key={s} active={filter === s} onClick={() => setFilter(s)}>
                {STATUS_META[s].label} {n}
              </FilterChip>
            );
          })}
        </div>

        {/* 列表 */}
        {loading ? (
          <div className="mt-4 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-xl bg-gray-200/70" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="mt-12 text-center text-sm text-gray-400">
            {apps.length === 0 ? '暂无投递记录' : '该状态下暂无记录'}
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {filtered.map((a) => (
              <div
                key={a.id}
                className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-2.5 shadow-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-gray-800">
                    {jobTitle(a.job_id)}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-gray-400">
                    {a.platform || '未知平台'} · {a.apply_date ?? a.created_at.slice(0, 10)}
                    {a.notes && ` · ${a.notes}`}
                  </div>
                </div>
                <select
                  className={`rounded-full border-0 px-2.5 py-1 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 ${STATUS_META[a.status]?.badge ?? 'bg-gray-100'}`}
                  value={a.status}
                  onChange={(e) => void changeStatus(a.id, e.target.value as ApplicationStatus)}
                >
                  {ALL_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_META[s].label}
                    </option>
                  ))}
                </select>
                <button
                  className="shrink-0 rounded-lg px-2 py-1 text-xs text-red-500 hover:bg-red-50"
                  onClick={() => void remove(a.id)}
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-center shadow-sm">
      <div className={`text-lg font-bold ${tone}`}>{value}</div>
      <div className="mt-0.5 text-xs text-gray-400">{label}</div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      className={`rounded-full px-3 py-1 text-xs transition ${
        active
          ? 'bg-blue-600 text-white'
          : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
