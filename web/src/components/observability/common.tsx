// 可观测平台通用 UI 原语（沿用 DashboardPage 范式：Skeleton / EmptyCard / ErrorCard）。
import type { ReactNode } from 'react';

export function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-gray-200/70 ${className ?? ''}`} />;
}

/** 卡片容器：统一圆角/边框/阴影 + 可选标题与右侧操作区 */
export function Card({
  title,
  action,
  children,
  className,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-gray-200 bg-white p-5 shadow-sm ${className ?? ''}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

/** 空数据引导卡（三态之"无数据"，绝不白屏） */
export function EmptyCard({ title, hint }: { title?: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 bg-white p-6 text-center shadow-sm">
      <h3 className="text-sm font-semibold text-gray-600">{title ?? '暂无数据'}</h3>
      <p className="mt-2 text-xs text-gray-400">
        {hint ?? '平台已就绪，发送一条聊天消息后将出现数据'}
      </p>
    </div>
  );
}

/** 错误卡 + 重试按钮（三态之"API 失败"，绝不白屏） */
export function ErrorCard({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
      <p className="text-sm font-medium text-red-700">数据加载失败</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
        >
          重试
        </button>
      )}
    </div>
  );
}

/** 小徽章 */
export function Pill({
  children,
  tone = 'gray',
}: {
  children: ReactNode;
  tone?: 'gray' | 'green' | 'amber' | 'red' | 'blue';
}) {
  const map: Record<string, string> = {
    gray: 'bg-gray-100 text-gray-600',
    green: 'bg-green-100 text-green-700',
    amber: 'bg-amber-100 text-amber-700',
    red: 'bg-red-100 text-red-700',
    blue: 'bg-blue-100 text-blue-700',
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${map[tone]}`}>{children}</span>
  );
}

/** 三态渲染：loading→Skeleton，error→ErrorCard，空→EmptyCard，否则渲染 children */
export function TriState({
  loading,
  error,
  empty,
  onRetry,
  emptyTitle,
  emptyHint,
  children,
}: {
  loading: boolean;
  error: boolean;
  empty: boolean;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyHint?: string;
  children: ReactNode;
}) {
  if (loading) return <Skeleton className="h-40" />;
  if (error) return <ErrorCard onRetry={onRetry} />;
  if (empty) return <EmptyCard title={emptyTitle} hint={emptyHint} />;
  return <>{children}</>;
}
