// 👍👎 反馈按钮（SDD §5.10.2/§5.10.5）：助手气泡 hover 显现 → POST /api/chat/feedback。
// rating=-1 触发后端 explicit_negative 规则进评审队列（US-F1）；👎 弹出可选 comment。
// "hover 显现" 由父级（ChatPanel）用 group/group-hover 控制，本组件只管交互与上报。
import { useState } from 'react';
import { submitFeedback } from '../../lib/api';

interface Props {
  conversationId?: number | null;
  messageId?: number | null;
  traceId?: string;
}

export default function FeedbackButtons({ conversationId, messageId, traceId }: Props) {
  const [sent, setSent] = useState<1 | -1 | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);

  const send = async (rating: 1 | -1, cmt?: string) => {
    if (busy) return;
    setBusy(true);
    await submitFeedback({
      rating,
      conversation_id: conversationId ?? undefined,
      message_id: messageId ?? undefined,
      trace_id: traceId ?? '',
      comment: cmt ?? '',
    });
    setBusy(false);
    setSent(rating);
    setShowComment(false);
  };

  if (sent !== null) {
    return (
      <div className="mt-1 text-xs text-gray-400">
        {sent === 1 ? '👍 已反馈，谢谢' : '👎 已收到，我们会改进'}
      </div>
    );
  }

  return (
    <div className="mt-1 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => void send(1)}
        disabled={busy}
        title="有帮助"
        className="rounded px-1.5 py-0.5 text-sm text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-40"
      >
        👍
      </button>
      <button
        type="button"
        onClick={() => setShowComment((v) => !v)}
        disabled={busy}
        title="有问题"
        className="rounded px-1.5 py-0.5 text-sm text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-40"
      >
        👎
      </button>
      {showComment && (
        <div className="flex items-center gap-1">
          <input
            autoFocus
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void send(-1, comment);
              if (e.key === 'Escape') setShowComment(false);
            }}
            placeholder="可选：说说哪里不好（Enter 提交）"
            className="w-56 rounded-lg border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="button"
            onClick={() => void send(-1, comment)}
            disabled={busy}
            className="rounded-lg bg-gray-600 px-2 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-40"
          >
            提交
          </button>
        </div>
      )}
    </div>
  );
}
