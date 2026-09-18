import { useState } from 'react';
import type { DiffCardData, DiffItem } from '../../../types/models';

/**
 * 简历修改对比卡片：before/after 双栏高亮 + 逐条确认。
 * 确认状态为前端本地回写（后端未提供确认持久化端点），实时统计已确认数。
 */
export default function DiffCard({ data }: { data: DiffCardData }) {
  const [items, setItems] = useState<DiffItem[]>(() => data.items ?? []);

  const toggle = (idx: number) => {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, confirmed: !it.confirmed } : it)),
    );
  };

  const confirmedCount = items.filter((it) => it.confirmed).length;
  const total = data.total_changes || items.length;

  return (
    <div className="my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">📝 简历修改对比</h3>
        <span className="text-xs text-gray-500">
          已确认 <b className="text-green-600">{confirmedCount}</b> / {total}
        </span>
      </div>

      <div className="mt-3 space-y-3">
        {items.map((item, idx) => (
          <div
            key={idx}
            className={`rounded-lg border p-3 ${
              item.confirmed ? 'border-green-300 bg-green-50/40' : 'border-gray-200'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                修改{idx + 1} · {item.section || '未分类'}
              </span>
              <button
                type="button"
                onClick={() => toggle(idx)}
                className={`shrink-0 rounded-lg px-3 py-1 text-xs font-medium text-white transition ${
                  item.confirmed ? 'bg-green-600 hover:bg-green-700' : 'bg-blue-600 hover:bg-blue-700'
                }`}
              >
                {item.confirmed ? '✓ 已确认' : '确认'}
              </button>
            </div>

            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="rounded-md bg-red-50 p-2">
                <div className="mb-1 text-[11px] font-semibold text-red-500">修改前</div>
                <div className="whitespace-pre-wrap text-xs leading-5 text-gray-700">{item.before}</div>
              </div>
              <div className="rounded-md bg-green-50 p-2">
                <div className="mb-1 text-[11px] font-semibold text-green-600">修改后</div>
                <div className="whitespace-pre-wrap text-xs leading-5 text-gray-700">{item.after}</div>
              </div>
            </div>

            {item.reason && (
              <div className="mt-2 text-xs text-gray-500">
                <b className="text-gray-600">原因：</b>
                {item.reason}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
