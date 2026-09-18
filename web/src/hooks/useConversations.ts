import { useCallback, useEffect, useState } from 'react';
import { deleteConversation, listConversations } from '../lib/api';
import type { ConversationSummary } from '../types/models';

/**
 * 会话列表管理：加载 / 刷新 / 删除。
 * 新建对话采用惰性策略（不预建空会话）：由 ChatPage 将 activeConvId 置空，
 * 首条消息发送后后端自动建会话并通过 data-conversation 事件回传 id。
 */
export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const list = await listConversations(50);
    setConversations(list ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = useCallback(
    async (id: number) => {
      const ok = await deleteConversation(id);
      if (ok) {
        setConversations((prev) => prev.filter((c) => c.id !== id));
      }
      return ok;
    },
    [],
  );

  return { conversations, loading, refresh, remove };
}
