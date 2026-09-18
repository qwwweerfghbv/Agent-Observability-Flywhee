import { useOutletContext } from 'react-router';
import ChatPanel from '../components/chat/ChatPanel';
import type { AppLayoutContext } from '../components/layout/AppLayout';

/**
 * 对话页：会话状态由 AppLayout 统一管理（通过 Outlet context 注入），
 * 本页仅渲染 ChatPanel，据 activeConvId 加载历史或开启新对话。
 */
export default function ChatPage() {
  const { activeConvId, onConvResolved } = useOutletContext<AppLayoutContext>();
  return <ChatPanel activeConvId={activeConvId} onConvResolved={onConvResolved} />;
}
