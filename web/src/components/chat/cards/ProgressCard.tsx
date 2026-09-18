import type { ProgressCardData } from '../../../types/models';

const R = 42;
const CIRCUMFERENCE = 2 * Math.PI * R;

/** 投递进度卡片：SVG 进度环 + 目标/已投/还需明细 + 鼓励语 */
export default function ProgressCard({ data }: { data: ProgressCardData }) {
  const target = Math.max(1, data.daily_target || 1);
  const applied = data.applied_today || 0;
  const pct = Math.max(0, Math.min(1, applied / target));
  const done = pct >= 1;

  return (
    <div className="my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-800">📈 今日投递进度</h3>
      <div className="mt-2 flex items-center gap-4">
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
            <span className="text-[10px] text-gray-400">/ {data.daily_target}</span>
          </div>
        </div>
        <div className="flex-1 space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">每日目标</span>
            <b>{data.daily_target}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">已投递</span>
            <b className="text-blue-600">{applied}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">还需投递</span>
            <b className="text-amber-600">{data.remaining}</b>
          </div>
        </div>
      </div>
      {data.encouragement && (
        <div className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-center text-sm text-blue-700">
          🔥 {data.encouragement}
        </div>
      )}
    </div>
  );
}
