import { useCallback, useState } from 'react';
import { Outlet, useNavigate } from 'react-router';
import AppSidebar from './AppSidebar';
import { useConversations } from '../../hooks/useConversations';

/**
 * 布局上下文：会话状态提升到布局层，供 ChatPage 通过 useOutletContext 消费。
 * activeConvId 为当前会话（null = 新对话）；onConvResolved 在新对话首条消息
 * 由后端回传 id 时高亮并刷新列表。
 */
export interface AppLayoutContext {
  activeConvId: number | null;
  onConvResolved: (id: number) => void;
}

/**
 * 应用外壳：左侧 AppSidebar（导航 + 会话历史）+ 右侧路由出口。
 * 会话状态在此集中管理，切换到会话/新建时自动导航回对话页（/）。
 */
export default function AppLayout() {
  const { conversations, refresh, remove } = useConversations();
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const navigate = useNavigate();

  const handleSelect = useCallback(
    (id: number) => {
      setActiveConvId(id);
      navigate('/');
    },
    [navigate],
  );

  const handleNew = useCallback(() => {
    setActiveConvId(null);
    navigate('/');
  }, [navigate]);

  const handleDelete = useCallback(
    async (id: number) => {
      if (!window.confirm('确定删除该对话？此操作不可恢复。')) return;
      const ok = await remove(id);
      if (ok && id === activeConvId) setActiveConvId(null);
    },
    [remove, activeConvId],
  );

  const handleConvResolved = useCallback(
    (id: number) => {
      setActiveConvId(id);
      void refresh();
    },
    [refresh],
  );

  const ctx: AppLayoutContext = { activeConvId, onConvResolved: handleConvResolved };

  return (
    <div className="flex h-screen bg-gray-50">
      <AppSidebar
        conversations={conversations}
        activeConvId={activeConvId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
      />
      <main className="min-w-0 flex-1">
        <Outlet context={ctx} />
      </main>
    </div>
  );
}
