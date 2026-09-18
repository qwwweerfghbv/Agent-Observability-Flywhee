import type { RecommendCardData } from '../../../types/models';

/** 岗位推荐卡片：标题/公司/薪资列表 */
export default function RecommendCard({ data }: { data: RecommendCardData }) {
  const jobs = data.jobs ?? [];
  return (
    <div className="my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-800">
        💼 推荐岗位
        <span className="ml-1 text-xs font-normal text-gray-400">共 {jobs.length} 个</span>
      </h3>
      <div className="mt-2 space-y-2">
        {jobs.map((job, i) => (
          <div
            key={job.id ?? i}
            className="flex items-center justify-between gap-2 rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2"
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-gray-800">{job.title}</div>
              <div className="truncate text-xs text-gray-500">{job.company}</div>
            </div>
            <span className="shrink-0 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
              {job.salary || '面议'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
