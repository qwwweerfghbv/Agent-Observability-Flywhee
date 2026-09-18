import { useRef, useState } from 'react';
import { uploadFiles, uploadImages } from '../../lib/api';

/** 待发送附件（已上传到后端，持有相对 url + 原始文件名） */
export interface PendingAttachment {
  url: string;
  filename: string;
}

interface Props {
  images: PendingAttachment[];
  files: PendingAttachment[];
  onImagesChange: (next: PendingAttachment[]) => void;
  onFilesChange: (next: PendingAttachment[]) => void;
  disabled?: boolean;
}

const IMAGE_ACCEPT = 'image/jpeg,image/jpg,image/png,image/webp,image/gif';
const FILE_ACCEPT = '.pdf,.doc,.docx,.txt,.md';
const MAX_IMAGES = 10;

/** 附件上传器：选择图片/文件 → 调后端上传 → 待发预览（可移除），发送时由 ChatPanel 携带 */
export default function AttachmentUploader({
  images,
  files,
  onImagesChange,
  onFilesChange,
  disabled,
}: Props) {
  const imgInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImages = async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const picked = Array.from(list);
    if (images.length + picked.length > MAX_IMAGES) {
      setError(`最多上传 ${MAX_IMAGES} 张图片`);
      return;
    }
    setError(null);
    setUploading(true);
    const res = await uploadImages(picked);
    setUploading(false);
    if (!res) {
      setError('图片上传失败');
      return;
    }
    onImagesChange([...images, ...res.images.map((im) => ({ url: im.url, filename: im.filename }))]);
  };

  const handleFiles = async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    setError(null);
    setUploading(true);
    const res = await uploadFiles(Array.from(list));
    setUploading(false);
    if (!res) {
      setError('文件上传失败');
      return;
    }
    onFilesChange([...files, ...res.files.map((f) => ({ url: f.url, filename: f.filename }))]);
  };

  const hasPending = images.length > 0 || files.length > 0;

  return (
    <div className="border-t border-gray-200 bg-white px-4 pt-2">
      <input
        ref={imgInput}
        type="file"
        accept={IMAGE_ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => {
          void handleImages(e.target.files);
          e.target.value = '';
        }}
      />
      <input
        ref={fileInput}
        type="file"
        accept={FILE_ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => {
          void handleFiles(e.target.files);
          e.target.value = '';
        }}
      />

      {hasPending && (
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {images.map((img, i) => (
            <span key={`img-${i}`} className="relative">
              <img
                src={img.url}
                alt={img.filename}
                className="h-12 w-12 rounded-md border border-gray-200 object-cover"
              />
              <button
                type="button"
                onClick={() => onImagesChange(images.filter((_, x) => x !== i))}
                className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] text-white hover:bg-red-600"
              >
                ✕
              </button>
            </span>
          ))}
          {files.map((f, i) => (
            <span
              key={`file-${i}`}
              className="flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600"
            >
              📎 {f.filename.length > 16 ? `${f.filename.slice(0, 16)}…` : f.filename}
              <button
                type="button"
                onClick={() => onFilesChange(files.filter((_, x) => x !== i))}
                className="text-gray-400 hover:text-red-500"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 pb-2">
        <button
          type="button"
          disabled={disabled || uploading}
          onClick={() => imgInput.current?.click()}
          className="rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-40"
        >
          🖼️ 图片
        </button>
        <button
          type="button"
          disabled={disabled || uploading}
          onClick={() => fileInput.current?.click()}
          className="rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-40"
        >
          📄 文件
        </button>
        {uploading && <span className="text-xs text-gray-400">上传中...</span>}
        {error && <span className="text-xs text-red-500">{error}</span>}
      </div>
    </div>
  );
}
