// 可复用错误边界（SDD §5.10.5）：main.tsx 全局包裹 + CardRenderer 单卡包裹。
// React 19 仍无 hook 版错误边界，用 class 组件；捕获后走 onError 回调上报 RUM。
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** 出错时渲染的兜底 UI（缺省渲染 null） */
  fallback?: ReactNode;
  /** 捕获回调：用于 reportRum 静默上报 */
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    try {
      this.props.onError?.(error, info);
    } catch {
      // 上报回调自身失败也不影响兜底渲染
    }
  }

  render() {
    if (this.state.hasError) return this.props.fallback ?? null;
    return this.props.children;
  }
}
