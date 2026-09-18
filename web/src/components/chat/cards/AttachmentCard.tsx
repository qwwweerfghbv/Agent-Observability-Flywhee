import type { AttachmentCardData } from '../../../types/models';

/**
 * 附件回显卡片：image_card 显示缩略图，file_card 显示下载链接。
 * url 为后端相对路径（/api/upload/...），dev 下经 vite proxy 同源可达。
 */
export default function AttachmentCard({
  kind,
  data,
}: {
  kind: 'image' | 'file';
  data: AttachmentCardData;
}) {
  if (!data.url) return null;
  const seq = (data.index ?? 0) + 1;

  if (kind === 'image') {
    return (
      <figure className="my-2 inline-block rounded-xl border border-gray-200 bg-white p-2 shadow-sm">
        <img
          src={data.url}
          alt={`图片 ${seq}`}
          className="max-h-48 rounded-lg object-contain"
        />
        <figcaption className="mt-1 text-center text-[11px] text-gray-400">图片 {seq}</figcaption>
      </figure>
    );
  }

  return (
    <a
      href={data.url}
      target="_blank"
      rel="noreferrer"
      className="my-2 inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-blue-600 shadow-sm hover:bg-blue-50"
    >
      📎 <span className="underline">查看文件 {seq}</span>
    </a>
  );
}
