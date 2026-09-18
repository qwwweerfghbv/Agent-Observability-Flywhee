import { NavLink } from 'react-router';
import type { ConversationSummary } from '../../types/models';
import { getObsSummary } from '../../lib/api';
import { usePolling } from '../../hooks/useObservability';
import type { SummaryResponse } from '../../types/observability';

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  obs?: boolean;
}

const navItems: NavItem[] = [
  { to: '/', label: '💬 对话', end: true },
  { to: '/dashboard', label: '📊 工作台' },
  { to: '/jobs', label: '💼 岗位管理' },
  { to: '/resumes', label: '📄 简历中心' },
  { to: '/applications', label: '📋 投递追踪' },
  { to: '/observability', label: '📡 可观测平台', obs: true },
  { to: '/settings', label: '⚙️ 设置' },
];

interface Props {
  conversations: ConversationSummary[];
  activeConvId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
}

/** 应用侧边栏：品牌 + 新对话 + 页面导航 + 会话历史（切换/删除） */
export default function AppSidebar({
  conversations,
  activeConvId,
  onSelect,
  onNew,
  onDelete,
}: Props) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
      <div className="p-4">
        <h1 className="text-lg font-bold">💬 求职Agent</h1>
        <button
          type="button"
          onClick={onNew}
          className="mt-3 w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          ➕ 新对话
        </button>
      </div>

      <nav className="flex flex-col gap-1 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `rounded-lg px-3 py-2 text-sm ${
                isActive ? 'bg-blue-50 font-medium text-blue-700' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <span className="flex items-center gap-1">
              {item.label}
              {item.obs && <ObsAlertBadge />}
            </span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-4 flex min-h-0 flex-1 flex-col border-t border-gray-100 pt-2">
        <div className="px-4 py-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
          📋 对话历史
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          {conversations.length === 0 && (
            <div className="px-2 py-3 text-xs text-gray-400">暂无历史对话</div>
          )}
          {conversations.map((c) => {
            const active = c.id === activeConvId;
            return (
              <div
                key={c.id}
                className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 ${
                  active ? 'bg-blue-50' : 'hover:bg-gray-100'
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  title={c.title}
                  className={`min-w-0 flex-1 truncate text-left text-sm ${
                    active ? 'font-medium text-blue-700' : 'text-gray-600'
                  }`}
                >
                  💬 {c.title || '新对话'}
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(c.id)}
                  title="删除对话"
                  className="shrink-0 rounded px-1 text-xs text-gray-300 opacity-0 transition hover:text-red-500 group-hover:opacity-100"
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

/** 可观测平台告警 badge：轮询 /summary 的 critical 告警数，为 0 或出错则不渲染（绝不干扰侧栏） */
function ObsAlertBadge() {
  const s = usePolling<SummaryResponse>(() => getObsSummary('24h'), 60000, []);
  if (s.error) return null;
  const critical = (s.data?.alerts ?? []).filter((a) => String(a.level) === 'critical').length;
  if (critical === 0) return null;
  return (
    <span
      className="ml-auto inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white"
      title={`${critical} 条未收敛 critical 告警`}
    >
      {critical > 99 ? '99+' : critical}
    </span>
  );
}
