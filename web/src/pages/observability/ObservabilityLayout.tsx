// 可观测平台布局（SDD §5.10.1）：ObsWindowContext + 页内子导航 + <Outlet/> 承载七视图。
// 时间窗切换经 Context 下发，触发全部子视图 usePolling 重取（§5.10.4）。
import { NavLink, Outlet } from 'react-router';
import { ObsWindowProvider, useObsWindow, WINDOWS } from '../../hooks/useObservability';
import type { ObsWindow } from '../../types/observability';

const TABS: { to: string; label: string; end?: boolean }[] = [
  { to: '/observability', label: '🏠 总览', end: true },
  { to: '/observability/monitor', label: '📈 运行监控' },
  { to: '/observability/traces', label: '🔗 链路查询' },
  { to: '/observability/quality', label: '🎯 质量哨兵' },
  { to: '/observability/review', label: '✅ 评审台' },
  { to: '/observability/reports', label: '📚 报告中心' },
  { to: '/observability/weekly', label: '🗓️ 飞轮周报' },
];

const WINDOW_LABEL: Record<ObsWindow, string> = {
  '1h': '1 小时',
  '24h': '24 小时',
  '7d': '7 天',
  '30d': '30 天',
};

export default function ObservabilityLayout() {
  return (
    <ObsWindowProvider>
      <ObsShell />
    </ObsWindowProvider>
  );
}

function ObsShell() {
  const { window, setWindow } = useObsWindow();
  return (
    <div className="flex h-full flex-col">
      <header className="shrink-0 border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold text-gray-800">📡 可观测平台</h1>
            <p className="text-xs text-gray-400">七层可观测 · 评测域链路 · BadCase 回流飞轮</p>
          </div>
          {/* 全局时间窗 */}
          <div className="flex items-center gap-0.5 rounded-lg bg-gray-100 p-0.5">
            {WINDOWS.map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => setWindow(w)}
                className={`rounded-md px-2.5 py-1 text-xs transition ${
                  window === w
                    ? 'bg-white font-medium text-blue-700 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {WINDOW_LABEL[w]}
              </button>
            ))}
          </div>
        </div>
        {/* 页内子导航 */}
        <nav className="mt-3 flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition ${
                  isActive
                    ? 'bg-blue-50 font-medium text-blue-700'
                    : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto bg-gray-50">
        <Outlet />
      </div>
    </div>
  );
}
