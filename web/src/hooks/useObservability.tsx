// 可观测平台取数 hooks（SDD §5.10.4）：轮询 + 全局时间窗。
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { ObsWindow } from '../types/observability';

// ---------- 全局时间窗（1h/24h/7d/30d）----------

interface ObsWindowCtx {
  window: ObsWindow;
  setWindow: (w: ObsWindow) => void;
}

const WindowContext = createContext<ObsWindowCtx>({ window: '24h', setWindow: () => {} });

export const WINDOWS: ObsWindow[] = ['1h', '24h', '7d', '30d'];

export function ObsWindowProvider({ children }: { children: ReactNode }) {
  const [window, setWindow] = useState<ObsWindow>('24h');
  return (
    <WindowContext.Provider value={{ window, setWindow }}>{children}</WindowContext.Provider>
  );
}

export function useObsWindow(): ObsWindowCtx {
  return useContext(WindowContext);
}

// ---------- 轮询取数 ----------

export interface PollingState<T> {
  data: T | null;
  loading: boolean;
  error: boolean;
  refresh: () => void;
}

/**
 * usePolling：按 intervalMs 轮询 fetcher，返回三态（loading/error/data）。
 * - fetcher 返回 null 视为错误态（getJSON 失败兜底），绝不白屏
 * - intervalMs<=0 或 enabled=false 时只取一次不轮询
 * - refresh() 立即重取（手动刷新/切时间窗调用）
 */
export function usePolling<T>(
  fetcher: () => Promise<T | null>,
  intervalMs = 60000,
  deps: unknown[] = [],
  enabled = true,
): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);
  const aliveRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    const res = await fetcherRef.current();
    if (!aliveRef.current) return;
    if (res === null) {
      setError(true);
    } else {
      setData(res);
      setError(false);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    setLoading(true);
    void run();
    let timer: ReturnType<typeof setInterval> | undefined;
    if (enabled && intervalMs > 0) {
      timer = setInterval(() => void run(), intervalMs);
    }
    return () => {
      aliveRef.current = false;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, enabled, tick, ...deps]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, refresh };
}
