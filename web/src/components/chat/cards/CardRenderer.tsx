import type { CardPayload } from '../../../types/models';
import ErrorBoundary from '../../ErrorBoundary';
import { reportRum } from '../../../lib/rum';
import ScoreCard from './ScoreCard';
import DiffCard from './DiffCard';
import QuestionCard from './QuestionCard';
import ProgressCard from './ProgressCard';
import RecommendCard from './RecommendCard';
import AttachmentCard from './AttachmentCard';

/** 单卡渲染失败占位（L6，SDD §5.10.5）：不拖死整条消息 */
function CardFallback({ type }: { type: string }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
      ⚠️ 卡片渲染失败（{type}），已静默上报
    </div>
  );
}

/** 按 card.type 分发；CardPayload 为判别联合，switch 后 card.data 自动收窄 */
function renderCard(card: CardPayload) {
  switch (card.type) {
    case 'score_card':
      return <ScoreCard data={card.data} />;
    case 'diff_card':
      return <DiffCard data={card.data} />;
    case 'question_card':
      return <QuestionCard data={card.data} />;
    case 'progress_card':
      return <ProgressCard data={card.data} />;
    case 'recommend_card':
      return <RecommendCard data={card.data} />;
    case 'image_card':
      return <AttachmentCard kind="image" data={card.data} />;
    case 'file_card':
      return <AttachmentCard kind="file" data={card.data} />;
    default:
      return null;
  }
}

/**
 * 卡片统一入口 + 单卡级 ErrorBoundary（L6）：
 * 渲染失败上报 card_render_fail 并显示占位块，不影响同条消息的其它内容。
 */
export default function CardRenderer({ card }: { card: CardPayload }) {
  const node = renderCard(card);
  if (node === null) return null;
  return (
    <ErrorBoundary
      fallback={<CardFallback type={card.type} />}
      onError={(err) =>
        reportRum({
          type: 'card_render_fail',
          card_type: card.type,
          message: err.message.slice(0, 200),
        })
      }
    >
      {node}
    </ErrorBoundary>
  );
}
