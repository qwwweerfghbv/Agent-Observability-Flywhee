import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import {
  deleteResume,
  getResumeDetail,
  listResumes,
  uploadResume,
} from '../lib/api';
import type { ResumeDetail, ResumeSummary } from '../types/models';

/**
 * 简历中心页（P3）：
 * - 文件上传解析（POST /api/resume/upload，PDF/DOCX/TXT，字段名 file）
 * - 简历列表 + 点击行懒加载详情（技能/工作/项目/教育）
 * - 删除简历
 */
export default function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, ResumeDetail | null>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const resp = await listResumes(50);
    setResumes(resp?.resumes ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onPickFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // 允许重复选择同一文件
    if (!file || uploading) return;
    setUploading(true);
    setMsg(null);
    const resp = await uploadResume(file);
    setUploading(false);
    if (resp) {
      setMsg({ ok: true, text: `${resp.message}：${resp.name}（识别 ${resp.skills_count} 项技能）` });
      void refresh();
    } else {
      setMsg({ ok: false, text: '上传解析失败，请确认格式（PDF/DOCX/TXT）与后端服务' });
    }
  };

  const toggleExpand = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!(id in details)) {
      const d = await getResumeDetail(id);
      setDetails((prev) => ({ ...prev, [id]: d }));
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm('确定删除该简历？')) return;
    const ok = await deleteResume(id);
    if (ok) {
      setResumes((prev) => prev.filter((r) => r.id !== id));
      if (expandedId === id) setExpandedId(null);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-6 py-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">📄 简历中心</h1>
            <p className="mt-1 text-sm text-gray-500">
              上传简历自动解析结构化；第一条为基础简历，用于岗位评分
            </p>
          </div>
          <button
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-40"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? '解析中...' : '⬆️ 上传简历'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={onPickFile}
          />
        </div>

        {msg && (
          <div
            className={`mt-4 rounded-lg px-3 py-2 text-sm ${
              msg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
            }`}
          >
            {msg.text}
          </div>
        )}

        {loading ? (
          <div className="mt-5 space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-200/70" />
            ))}
          </div>
        ) : resumes.length === 0 ? (
          <div className="mt-16 text-center text-sm text-gray-400">
            暂无简历，点击右上角「上传简历」开始
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            {resumes.map((r, idx) => (
              <div key={r.id} className="rounded-xl border border-gray-200 bg-white shadow-sm">
                <div
                  className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-gray-50"
                  onClick={() => void toggleExpand(r.id)}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-gray-800">
                      {r.name || '未识别姓名'}
                      {idx === 0 && (
                        <span className="ml-2 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                          基础简历
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-xs text-gray-400">
                      {r.location || '地点未知'} · {r.years_of_experience ?? 0}年经验 ·{' '}
                      {r.created_at ? r.created_at.slice(0, 10) : ''}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-gray-400">
                      {expandedId === r.id ? '▲' : '▼'}
                    </span>
                    <button
                      className="rounded-lg px-2 py-1 text-xs text-red-500 hover:bg-red-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        void remove(r.id);
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
                {expandedId === r.id && (
                  <div className="border-t border-gray-100 px-4 py-3">
                    <ResumeDetailPanel detail={details[r.id]} />
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

/** 简历详情面板：技能 chips + 工作经历 + 项目 + 教育 */
function ResumeDetailPanel({ detail }: { detail: ResumeDetail | null | undefined }) {
  if (detail === undefined) {
    return <div className="py-2 text-xs text-gray-400">加载中...</div>;
  }
  if (detail === null) {
    return <div className="py-2 text-xs text-red-500">详情加载失败</div>;
  }
  const d = detail.data;
  return (
    <div className="space-y-3 text-sm">
      {d.summary && <p className="text-gray-600">{d.summary}</p>}
      {(d.skills ?? []).length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold text-gray-500">技能</div>
          <div className="flex flex-wrap gap-1.5">
            {(d.skills ?? []).map((s, i) => (
              <span
                key={i}
                className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700"
              >
                {s.name}
                {s.level ? ` · ${s.level}` : ''}
              </span>
            ))}
          </div>
        </div>
      )}
      {(d.work_experiences ?? []).length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-500">工作经历</div>
          {(d.work_experiences ?? []).map((w, i) => (
            <div key={i} className="mb-2">
              <div className="font-medium text-gray-700">
                {w.company} · {w.position}
                <span className="ml-2 text-xs font-normal text-gray-400">
                  {w.start_date} - {w.end_date || '至今'}
                </span>
              </div>
              {w.description && <div className="mt-0.5 text-gray-600">{w.description}</div>}
              {(w.achievements ?? []).map((a, j) => (
                <div key={j} className="mt-0.5 text-xs text-green-700">✓ {a}</div>
              ))}
            </div>
          ))}
        </div>
      )}
      {(d.projects ?? []).length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-500">项目经历</div>
          {(d.projects ?? []).map((p, i) => (
            <div key={i} className="mb-2">
              <div className="font-medium text-gray-700">
                {p.name}
                {p.role && <span className="ml-2 text-xs font-normal text-gray-400">{p.role}</span>}
              </div>
              {p.description && <div className="mt-0.5 text-gray-600">{p.description}</div>}
              {(p.technologies ?? []).length > 0 && (
                <div className="mt-1 text-xs text-gray-400">
                  技术栈: {(p.technologies ?? []).join(' / ')}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {(d.educations ?? []).length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-500">教育背景</div>
          {(d.educations ?? []).map((e, i) => (
            <div key={i} className="text-gray-600">
              {e.school} · {e.degree} · {e.major}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
