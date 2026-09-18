import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { reportRum, stackSummary } from './lib/rum';
import './index.css';

// ============================================================
// L6 RUM 全局挂载（SDD §5.10.5）：JS 错误 / 未处理 rejection 静默上报。
// 隐私约束：只取 message + 栈首帧，不含 DOM 内容与消息全文。
// ============================================================
window.addEventListener('error', (e) => {
  reportRum({
    type: 'js_error',
    message: (e.message || 'window.error').slice(0, 200),
    stack_summary: stackSummary(e.error?.stack),
  });
});

window.addEventListener('unhandledrejection', (e) => {
  const r = e.reason;
  const msg = r instanceof Error ? r.message : String(r);
  reportRum({
    type: 'js_error',
    message: `unhandledrejection: ${msg}`.slice(0, 200),
    stack_summary: stackSummary(r instanceof Error ? r.stack : null),
  });
});

/** 全局渲染错误兜底 UI（绝不白屏） */
function GlobalFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-gray-50 p-6">
      <div className="max-w-md rounded-xl border border-red-200 bg-white p-6 text-center shadow-sm">
        <p className="text-sm font-semibold text-red-700">页面出现异常</p>
        <p className="mt-2 text-xs text-gray-500">错误已静默上报，请刷新页面重试。</p>
        <button
          type="button"
          onClick={() => location.reload()}
          className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
        >
          刷新页面
        </button>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary
      fallback={<GlobalFallback />}
      onError={(err) =>
        reportRum({
          type: 'js_error',
          message: `render: ${err.message}`.slice(0, 200),
          stack_summary: stackSummary(err.stack),
        })
      }
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
