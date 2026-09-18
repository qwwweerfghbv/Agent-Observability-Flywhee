import { useEffect, useState } from 'react';
import { getPreferences, updatePreferences } from '../lib/api';
import type { SettingsUpdate } from '../types/models';

const PROVIDERS = ['qwen', 'openai', 'deepseek', 'zhipu', 'ollama'];

/** 表单原始态：全部以字符串编辑，保存时再转换（数字/列表/日期） */
interface RawForm {
  target_city: string;
  expected_salary_min: string;
  daily_apply_target: string;
  job_start_date: string;
  llm_provider: string;
  llm_model: string;
  target_positions: string; // 逗号分隔
  excluded_keywords: string; // 逗号分隔
}

const EMPTY: RawForm = {
  target_city: '',
  expected_salary_min: '',
  daily_apply_target: '',
  job_start_date: '',
  llm_provider: 'qwen',
  llm_model: '',
  target_positions: '',
  excluded_keywords: '',
};

/** 逗号（中英文）分隔字符串 → 去空数组 */
function parseList(text: string): string[] {
  return text
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** 设置页：加载用户偏好表单，保存 PUT /api/settings */
export default function SettingsPage() {
  const [form, setForm] = useState<RawForm>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const prefs = await getPreferences();
      if (!alive) return;
      if (prefs) {
        setForm({
          target_city: prefs.target_city ?? '',
          expected_salary_min: String(prefs.expected_salary_min ?? ''),
          daily_apply_target: String(prefs.daily_apply_target ?? ''),
          job_start_date: prefs.job_start_date ?? '',
          llm_provider: prefs.llm_provider ?? 'qwen',
          llm_model: prefs.llm_model ?? '',
          target_positions: (prefs.target_positions ?? []).join(', '),
          excluded_keywords: (prefs.excluded_keywords ?? []).join(', '),
        });
      }
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const set = (key: keyof RawForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    const payload: SettingsUpdate = {
      target_city: form.target_city,
      expected_salary_min: Number(form.expected_salary_min) || 0,
      daily_apply_target: Number(form.daily_apply_target) || 0,
      job_start_date: form.job_start_date || null,
      llm_provider: form.llm_provider,
      llm_model: form.llm_model,
      target_positions: parseList(form.target_positions),
      excluded_keywords: parseList(form.excluded_keywords),
    };
    const res = await updatePreferences(payload);
    setSaving(false);
    if (res) {
      setMsg({ kind: 'ok', text: '✅ 设置已保存' });
    } else {
      setMsg({ kind: 'err', text: '❌ 保存失败，请检查后端服务' });
    }
  }

  const providerOptions = PROVIDERS.includes(form.llm_provider)
    ? PROVIDERS
    : [form.llm_provider, ...PROVIDERS];

  if (loading) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-2xl px-6 py-6">
          <div className="h-6 w-32 animate-pulse rounded bg-gray-200" />
          <div className="mt-5 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-gray-200/70" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <form onSubmit={handleSave} className="mx-auto max-w-2xl px-6 py-6">
        <h1 className="text-xl font-bold text-gray-800">⚙️ 设置</h1>
        <p className="mt-1 text-sm text-gray-500">配置求职目标、岗位偏好与模型参数</p>

        {/* 求职目标 */}
        <Section title="🎯 求职目标">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="目标城市">
              <input className={inputCls} value={form.target_city} onChange={set('target_city')} placeholder="如：杭州" />
            </Field>
            <Field label="期望最低总包（万/年）">
              <input className={inputCls} type="number" min={0} value={form.expected_salary_min} onChange={set('expected_salary_min')} />
            </Field>
            <Field label="每日投递目标">
              <input className={inputCls} type="number" min={0} value={form.daily_apply_target} onChange={set('daily_apply_target')} />
            </Field>
            <Field label="求职开始日期">
              <input className={inputCls} type="date" value={form.job_start_date} onChange={set('job_start_date')} />
            </Field>
          </div>
        </Section>

        {/* 岗位偏好 */}
        <Section title="💼 岗位偏好">
          <Field label="目标岗位方向" hint="多个用逗号分隔">
            <input className={inputCls} value={form.target_positions} onChange={set('target_positions')} placeholder="AI测试开发, AI Agent评测" />
          </Field>
          <Field label="排除关键词" hint="多个用逗号分隔">
            <input className={inputCls} value={form.excluded_keywords} onChange={set('excluded_keywords')} placeholder="外包" />
          </Field>
        </Section>

        {/* 模型设置 */}
        <Section title="🤖 模型设置">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="LLM 提供商">
              <select className={inputCls} value={form.llm_provider} onChange={set('llm_provider')}>
                {providerOptions.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="LLM 模型">
              <input className={inputCls} value={form.llm_model} onChange={set('llm_model')} placeholder="qwen-plus" />
            </Field>
          </div>
        </Section>

        {/* 保存区 */}
        <div className="mt-6 flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? '保存中...' : '💾 保存设置'}
          </button>
          {msg && (
            <span className={`text-sm ${msg.kind === 'ok' ? 'text-green-600' : 'text-red-500'}`}>
              {msg.text}
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

const inputCls =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold text-gray-700">{title}</h2>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600">
        {label}
        {hint && <span className="ml-1 font-normal text-gray-400">（{hint}）</span>}
      </span>
      {children}
    </label>
  );
}
