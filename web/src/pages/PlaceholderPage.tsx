export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center text-gray-400">
        <h2 className="mb-2 text-2xl">{title}</h2>
        <p>页面开发中（保持占位）</p>
      </div>
    </div>
  );
}
