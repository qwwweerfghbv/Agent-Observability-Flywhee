import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { useEffect, useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getConversationDetail } from '../../lib/api';
import { toUIMessages } from '../../lib/messages';
import type { JobAgentUIMessage } from '../../types/models';
import AttachmentUploader, { type PendingAttachment } from './AttachmentUploader';
import CardRenderer from './cards/CardRenderer';
import FeedbackButtons from '../observability/FeedbackButtons';

interface Props {
  /** 当前选中会话（null = 新对话，首条消息后由后端创建） */
  activeConvId: number | null;
  /** 后端为新对话分配 id 后回调（父级据此高亮 + 刷新列表） */
  onConvResolved: (id: number) => void;
}

/**
 * 对话面板：useChat 消费后端 /api/chat/ai-stream（AI SDK UI Message Stream 协议）。
 * - 流式打字机（text-delta）+ 中断生成（stop）
 * - data-card → CardRenderer 富卡片渲染
 * - data-conversation → 回收会话ID，多轮保持同一会话
 * - activeConvId 切换 → 加载历史并复原卡片；置空 → 开启新对话
 * - 附件：AttachmentUploader 上传后暂存，发送时随 body 携带 image_paths/file_paths
 */
export default function ChatPanel({ activeConvId, onConvResolved }: Props) {
  const [input, setInput] = useState('');
  const [pendingImages, setPendingImages] = useState<PendingAttachment[]>([]);
  const [pendingFiles, setPendingFiles] = useState<PendingAttachment[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const conversationIdRef = useRef<number | null>(null);
  const resolvedRef = useRef<number | null>(null);
  const imagesRef = useRef<PendingAttachment[]>([]);
  const filesRef = useRef<PendingAttachment[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 保持 ref 与最新待发附件同步（供 prepareSendMessagesRequest 读取，规避闭包陈旧）
  imagesRef.current = pendingImages;
  filesRef.current = pendingFiles;

  const { messages, sendMessage, setMessages, status, stop } = useChat<JobAgentUIMessage>({
    transport: new DefaultChatTransport<JobAgentUIMessage>({
      api: '/api/chat/ai-stream',
      prepareSendMessagesRequest: ({ messages }) => {
        const last = messages[messages.length - 1];
        const text = last.parts
          .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
          .map((p) => p.text)
          .join('');
        const imgs = imagesRef.current.map((i) => i.url);
        const fils = filesRef.current.map((f) => f.url);
        // 读取后清空待发附件（发送时机，无竞态）
        if (imgs.length || fils.length) {
          imagesRef.current = [];
          filesRef.current = [];
          setPendingImages([]);
          setPendingFiles([]);
        }
        return {
          body: {
            conversation_id: conversationIdRef.current,
            message: text,
            image_paths: imgs.length ? imgs : null,
            file_paths: fils.length ? fils : null,
          },
        };
      },
    }),
  });

  // 回收后端下发的会话ID；仅当 id 变化时通知父级（避免流式期间每帧重复刷新列表）
  useEffect(() => {
    for (const m of messages) {
      for (const p of m.parts) {
        if (p.type === 'data-conversation') {
          const id = p.data.conversation_id;
          conversationIdRef.current = id;
          if (resolvedRef.current !== id) {
            resolvedRef.current = id;
            onConvResolved(id);
          }
        }
      }
    }
  }, [messages, onConvResolved]);

  // 会话切换：activeConvId 与当前不同才重载（新对话刚分配 id 时二者相等 → 跳过，保留在途消息）
  useEffect(() => {
    if (activeConvId === conversationIdRef.current) return;
    conversationIdRef.current = activeConvId;
    resolvedRef.current = activeConvId;
    if (activeConvId === null) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setLoadingHistory(true);
    void getConversationDetail(activeConvId).then((detail) => {
      if (cancelled) return;
      setMessages(detail ? toUIMessages(detail) : []);
      setLoadingHistory(false);
    });
    return () => {
      cancelled = true;
    };
  }, [activeConvId, setMessages]);

  // 新内容自动滚底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const busy = status === 'submitted' || status === 'streaming';

  const submit = () => {
    const text = input.trim();
    if (!text || busy) return;
    sendMessage({ text });
    setInput('');
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
        {messages.length === 0 && !loadingHistory && (
          <div className="pt-24 text-center text-gray-400">
            <p className="mb-2 text-2xl">💬 求职Agent</p>
            <p>发送消息开始：优化简历 / 评估岗位 / 模拟面试</p>
          </div>
        )}
        {loadingHistory && (
          <div className="pt-24 text-center text-sm text-gray-400">加载历史对话...</div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`group flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            {m.parts.map((part, i) => {
              if (part.type === 'text') {
                if (!part.text) return null;
                return m.role === 'user' ? (
                  <div
                    key={i}
                    className="max-w-[75%] whitespace-pre-wrap rounded-2xl bg-blue-600 px-4 py-2 text-sm leading-6 text-white"
                  >
                    {part.text}
                  </div>
                ) : (
                  <div
                    key={i}
                    className="max-w-[85%] rounded-2xl border border-gray-200 bg-white px-4 py-2 text-sm leading-6"
                  >
                    <div className="prose prose-sm max-w-none">
                      <Markdown remarkPlugins={[remarkGfm]}>{part.text}</Markdown>
                    </div>
                  </div>
                );
              }
              if (part.type === 'data-card') {
                return (
                  <div key={part.id ?? `card-${i}`} className="w-full max-w-[85%]">
                    <CardRenderer card={part.data} />
                  </div>
                );
              }
              return null;
            })}
            {m.role === 'assistant' && !busy && (
              <div className="max-w-[85%] opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
                <FeedbackButtons conversationId={conversationIdRef.current} />
              </div>
            )}
          </div>
        ))}

        {status === 'submitted' && <div className="text-sm text-gray-400">思考中...</div>}
        {status === 'error' && (
          <div className="text-sm text-red-500">请求失败，请检查后端服务后重试</div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="bg-white">
        <AttachmentUploader
          images={pendingImages}
          files={pendingFiles}
          onImagesChange={setPendingImages}
          onFilesChange={setPendingFiles}
          disabled={busy}
        />
        <form
          className="flex gap-2 px-4 pb-4 pt-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <textarea
            className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
            placeholder="输入消息...（Ctrl+Enter 发送）"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <div className="flex items-end">
            {status === 'streaming' ? (
              <button
                type="button"
                onClick={stop}
                className="rounded-xl bg-red-500 px-5 py-2 text-sm text-white hover:bg-red-600"
              >
                ⏹ 停止
              </button>
            ) : (
              <button
                type="submit"
                disabled={busy || !input.trim()}
                className="rounded-xl bg-blue-600 px-5 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-40"
              >
                发送
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
