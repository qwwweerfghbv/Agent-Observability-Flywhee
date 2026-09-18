import { useEffect, useState } from 'react';
import {
  getBeliefToday,
  getDailyProgress,
  getJobSeekingStats,
} from '../lib/api';
import type { DailyBelief, DailyProgress, JobSeekingStats } from '../types/models';

const R = 42;
const CIRCUMFERENCE = 2 * Math.PI * R;

/** 信念分类 → 中文标签 / 配色 / 图标 */
const CATEGORY: Record<
  string,
  { label: string; badge: string; grad: string; icon: string }
> = {
  persist: { label: '坚持', badge: 'bg-blue-100 text-blue-700', grad: 'from-blue-50 to-indigo-50', icon: '🔥' },
  confidence: { label: '自信', badge: 'bg-purple-100 text-purple-700', grad: 'from-purple-50 to-pink-50', icon: '💪' },
  growth: { label: '成长', badge: 'bg-green-100 text-green-700', grad: 'from-green-50 to-emerald-50', icon: '🌱' },
  expression: { label: '表达', badge: 'bg-amber-100 text-amber-700', grad: 'from-amber-50 to-orange-50', icon: '🗣️' },
};

/** 工作台：今日信念 + 求职统计 + 今日投递进度三卡 */
export default function DashboardPage() {
  const [belief, setBelief] = useState<DailyBelief | null>(null);
  const [stats, setStats] = useState<JobSeekingStats | null>(null);
  const [progress, setProgress] = useState<DailyProgress | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [b, s, p] = await Promise.all([
        getBeliefToday(),
        getJobSeekingStats(),
        getDailyProgress(),
      ]);
      if (!alive) return;
      setBelief(b);
      setStats(s);
      setProgress(p);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-6">
        <h1 className="text-xl font-bold text-gray-800">📊 工作台</h1>
        <p className="mt-1 text-sm text-gray-500">求职进度总览与每日信念</p>

        {loading ? (
          <div className="mt-6 space-y-4">
            <Skeleton className="h-32" />
            <div className="grid gap-4 md:grid-cols-2">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          </div>
        ) : (
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {/* 今日信念（跨两列） */}
            <div className="md:col-span-2">
              <BeliefCard belief={belief} />
            </div>
            <StatsCard stats={stats} />
            <ProgressCard progress={progress} />
          </div>
        )}
      </div>
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-gray-200/70 ${className ?? ''}`} />;
}

/** 今日信念卡：分类图标 + 内容 + 分类徽章 */
function BeliefCard({ belief }: { belief: DailyBelief | null }) {
  if (!belief) {
    return <EmptyCard title="🔥 今日信念" hint="暂无信念数据" />;
  }
  const cat = CATEGORY[belief.category] ?? {
    label: belief.category || '信念',
    badge: 'bg-gray-100 text-gray-600',
    grad: 'from-gray-50 to-slate-50',
    icon: '✨',
  };
  return (
    <div
      className={`rounded-xl border border-gray-200 bg-gradient-to-br p-5 shadow-sm ${cat.grad}`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">🔥 今日信念</h3>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${cat.badge}`}>
          {cat.icon} {cat.label}
        </span>
      </div>
      <p className="mt-3 text-lg font-medium leading-8 text-gray-800">{belief.content}</p>
    </div>
  );
}

/** 求职统计卡：天数（大数字）+ 累计投递 / 面试 / offer */
function StatsCard({ stats }: { stats: JobSeekingStats | null }) {
  if (!stats) {
    return <EmptyCard title="📈 求职统计" hint="暂无统计数据" />;
  }
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700">📈 求职统计</h3>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-4xl font-bold text-blue-600">{stats.days_count}</span>
        <span className="text-sm text-gray-400">天</span>
        <span className="ml-1 text-xs text-gray-400">求职进行中</span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-gray-100 pt-3 text-center">
        <StatItem label="累计投递" value={stats.total_applied} tone="text-gray-800" />
        <StatItem label="面试次数" value={stats.interview_count} tone="text-amber-600" />
        <StatItem label="Offer" value={stats.offer_count} tone="text-green-600" />
      </div>
    </div>
  );
}

function StatItem({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <div className={`text-xl font-bold ${tone}`}>{value}</div>
      <div className="mt-0.5 text-xs text-gray-400">{label}</div>
    </div>
  );
}

/** 今日进度卡：SVG 进度环 + 明细 + 鼓励语 */
function ProgressCard({ progress }: { progress: DailyProgress | null }) {
  if (!progress) {
    return <EmptyCard title="🎯 今日进度" hint="暂无进度数据" />;
  }
  const target = Math.max(1, progress.daily_target || 1);
  const applied = progress.applied_today || 0;
  const pct = Math.max(0, Math.min(1, applied / target));
  const done = pct >= 1;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700">🎯 今日投递进度</h3>
      <div className="mt-3 flex items-center gap-4">
        <div className="relative h-24 w-24 shrink-0">
          <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            <circle cx="50" cy="50" r={R} fill="none" stroke="#eef2f7" strokeWidth="10" />
            <circle
              cx="50"
              cy="50"
              r={R}
              fill="none"
              stroke={done ? '#16a34a' : '#2563eb'}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={CIRCUMFERENCE * (1 - pct)}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-gray-800">{applied}</span>
            <span className="text-[10px] text-gray-400">/ {progress.daily_target}</span>
          </div>
        </div>
        <div className="flex-1 space-y-1.5 text-sm">
          <Row label="每日目标" value={progress.daily_target} tone="text-gray-800" />
          <Row label="有效投递" value={progress.valid_applied} tone="text-green-600" />
          <Row label="还需投递" value={progress.remaining} tone="text-amber-600" />
        </div>
      </div>
      {progress.encouragement && (
        <div className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-center text-sm text-blue-700">
          🔥 {progress.encouragement}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <b className={tone}>{value}</b>
    </div>
  );
}

function EmptyCard({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 bg-white p-5 text-center shadow-sm">
      <h3 className="text-sm font-semibold text-gray-600">{title}</h3>
      <p className="mt-2 text-xs text-gray-400">{hint}</p>
    </div>
  );
}
