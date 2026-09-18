import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { deleteJob, getJobDetail, listJobs, parseJob } from '../lib/api';
import type { JobDetail, JobSummary } from '../types/models';

/**
 * 岗位管理页（P3）：
 * - JD 粘贴解析入库（POST /api/job/parse，LLM 解析约 5-20s）
 * - 岗位列表 + 点击行懒加载详情（技能要求/职责/福利）
 * - 删除岗位
 */
export default function JobsPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [jdText, setJdText] = useState('');
  const [parsing, setParsing] = useState(false);
  const [parseMsg, setParseMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, JobDetail | null>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    const resp = await listJobs(50);
    setJobs(resp?.jobs ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toggleExpand = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!(id in details)) {
      const d = await getJobDetail(id);
      setDetails((prev) => ({ ...prev, [id]: d }));
    }
  };

  const submitParse = async () => {
    if (!jdText.trim() || parsing) return;
    setParsing(true);
    setParseMsg(null);
    const resp = await parseJob(jdText.trim());
    setParsing(false);
    if (resp) {
      setParseMsg({ ok: true, text: `解析成功：${resp.data.title} @ ${resp.data.company}` });
      setJdText('');
      setShowForm(false);
      void refresh();
    } else {
      setParseMsg({ ok: false, text: '解析失败，请检查 JD 文本或后端服务' });
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm('确定删除该岗位？关联的评分记录将不可见。')) return;
    const ok = await deleteJob(id);
    if (ok) {
      setJobs((prev) => prev.filter((j) => j.id !== id));
      if (expandedId === id) setExpandedId(null);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">💼 岗位管理</h1>
            <p className="mt-1 text-sm text-gray-500">粘贴 JD 解析入库，点击行查看详情</p>
          </div>
          <button
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? '收起' : '➕ 解析 JD'}
          </button>
        </div>

        {parseMsg && (
          <div
            className={`mt-4 rounded-lg px-3 py-2 text-sm ${
              parseMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
            }`}
          >
            {parseMsg.text}
          </div>
        )}

        {showForm && (
          <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <textarea
              className="w-full resize-y rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={8}
              placeholder="粘贴完整 JD 文本（岗位名称/公司/职责/要求/薪资...），LLM 解析约需 5-20 秒"
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
            />
            <div className="mt-2 flex justify-end">
              <button
                className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-40"
                disabled={!jdText.trim() || parsing}
                onClick={submitParse}
              >
                {parsing ? '解析中...' : '解析并入库'}
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="mt-5 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-200/70" />
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="mt-16 text-center text-sm text-gray-400">
            暂无岗位，点击右上角「解析 JD」录入第一个岗位
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            {jobs.map((j) => (
              <div key={j.id} className="rounded-xl border border-gray-200 bg-white shadow-sm">
                <div
                  className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-gray-50"
                  onClick={() => void toggleExpand(j.id)}
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-gray-800">
                      {j.title}
                      <span className="ml-2 font-normal text-gray-500">@ {j.company}</span>
                    </div>
                    <div className="mt-0.5 text-xs text-gray-400">
                      {j.location || '地点未知'} · {j.salary || '面议'} ·{' '}
                      {j.created_at ? j.created_at.slice(0, 10) : ''}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-gray-400">
                      {expandedId === j.id ? '▲' : '▼'}
                    </span>
                    <button
                      className="rounded-lg px-2 py-1 text-xs text-red-500 hover:bg-red-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        void remove(j.id);
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
                {expandedId === j.id && (
                  <div className="border-t border-gray-100 px-4 py-3">
                    <JobDetailPanel detail={details[j.id]} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** 岗位详情面板：技能要求 chips + 职责 + 福利 */
function JobDetailPanel({ detail }: { detail: JobDetail | null | undefined }) {
  if (detail === undefined) {
    return <div className="py-2 text-xs text-gray-400">加载中...</div>;
  }
  if (detail === null) {
    return <div className="py-2 text-xs text-red-500">详情加载失败</div>;
  }
  const d = detail.data;
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap gap-2 text-xs text-gray-500">
        {d.years_required != null && <Tag>经验：{d.years_required}年</Tag>}
        {d.education_required && <Tag>学历：{d.education_required}</Tag>}
        {d.salary_min != null && d.salary_max != null && (
          <Tag>薪资：{d.salary_min}-{d.salary_max}万</Tag>
        )}
        {d.industry && <Tag>行业：{d.industry}</Tag>}
      </div>
      {(d.requirements ?? []).length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold text-gray-500">技能要求</div>
          <div className="flex flex-wrap gap-1.5">
            {(d.requirements ?? []).map((r, i) => (
              <span
                key={i}
                className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700"
              >
                {r.skill}
              </span>
            ))}
          </div>
        </div>
      )}
      {(d.responsibilities ?? []).length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-500">岗位职责</div>
          <ul className="list-inside list-disc space-y-0.5 text-gray-600">
            {(d.responsibilities ?? []).map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      {(d.benefits ?? []).length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-500">福利</div>
          <div className="flex flex-wrap gap-1.5">
            {(d.benefits ?? []).map((b, i) => (
              <Tag key={i}>{b}</Tag>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600">
      {children}
    </span>
  );
}
