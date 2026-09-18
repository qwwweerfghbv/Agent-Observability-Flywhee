// 状态灯（SDD §5.10.2）：🟢🟡🔴⚪，点击可跳转对应监控分区。
import type { LayerStatus, SloState } from '../../types/observability';

const DOT: Record<string, string> = {
  green: 'bg-green-500',
  ok: 'bg-green-500',
  warning: 'bg-amber-400',
  critical: 'bg-red-500',
  unknown: 'bg-gray-300',
  no_data: 'bg-gray-300',
};

const LABEL: Record<string, string> = {
  green: '正常',
  ok: '达标',
  warning: '警告',
  critical: '严重',
  unknown: '未知',
  no_data: '无数据',
};

/** 归一化：SloState / LayerStatus → 灯色 key */
export function lightKey(s?: LayerStatus | SloState | string): string {
  if (!s) return 'unknown';
  return DOT[s] ? s : 'unknown';
}

export default function StatusLight({
  status,
  label,
  onClick,
  size = 'md',
}: {
  status?: LayerStatus | SloState | string;
  label?: string;
  onClick?: () => void;
  size?: 'sm' | 'md';
}) {
  const key = lightKey(status);
  const dim = size === 'sm' ? 'h-2 w-2' : 'h-3 w-3';
  const dot = (
    <span
      className={`inline-block shrink-0 rounded-full ${DOT[key]} ${dim}`}
      title={LABEL[key] ?? key}
    />
  );
  if (!onClick) {
    return (
      <span className="inline-flex items-center gap-1.5">
        {dot}
        {label && <span className="text-xs text-gray-500">{label}</span>}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded px-1 py-0.5 hover:bg-gray-100"
    >
      {dot}
      {label && <span className="text-xs text-gray-600">{label}</span>}
    </button>
  );
}
