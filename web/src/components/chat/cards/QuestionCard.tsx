import type { QuestionCardData } from '../../../types/models';

const TYPE_LABEL: Record<string, string> = {
  technical: '技术面',
  behavioral: '行为面',
  hr: 'HR面',
};

/** 面试题卡片：原生 details 折叠面板，展开显示考察点/难度/参考答案 */
export default function QuestionCard({ data }: { data: QuestionCardData }) {
  const questions = data.questions ?? [];
  return (
    <div className="my-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-800">
        🎯 {TYPE_LABEL[data.interview_type] ?? data.interview_type}面试题
        <span className="ml-1 text-xs font-normal text-gray-400">共 {questions.length} 道</span>
      </h3>
      <div className="mt-2 space-y-2">
        {questions.map((q, i) => (
          <details
            key={i}
            className="group rounded-lg border border-gray-200 bg-gray-50/50 open:bg-white"
          >
            <summary className="flex cursor-pointer list-none items-start gap-2 px-3 py-2 text-sm text-gray-700 [&::-webkit-details-marker]:hidden">
              <span className="shrink-0 rounded bg-blue-100 px-1.5 text-xs font-semibold text-blue-700">
                {i + 1}
              </span>
              <span className="flex-1">{q.question}</span>
              <span className="shrink-0 text-gray-400 transition-transform group-open:rotate-90">▸</span>
            </summary>
            <div className="border-t border-gray-100 px-3 py-2 text-xs">
              <div className="flex flex-wrap gap-2">
                {q.skill && (
                  <span className="rounded bg-purple-50 px-2 py-0.5 text-purple-600">考察：{q.skill}</span>
                )}
                {q.difficulty && (
                  <span className="rounded bg-amber-50 px-2 py-0.5 text-amber-600">难度：{q.difficulty}</span>
                )}
              </div>
              {q.reference_answer && (
                <div className="mt-2 rounded-md bg-green-50/60 p-2 leading-5 text-gray-700">
                  <b className="text-green-700">参考答案：</b>
                  {q.reference_answer}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
