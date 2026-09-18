"""对话API - SDD"""
import asyncio
import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from loguru import logger
from pydantic import BaseModel

from app.models.conversation import (
    ChatRequest, ChatResponse, ConversationCreate, ConversationResponse,
    ConversationDetail
)
from app.observability.context import fill, get_context
from app.observability.writers import stream_metrics, write_request, write_rum
from app.services.chat_engine import ChatEngineService

router = APIRouter(prefix="/api/chat", tags=["对话"])

chat_service = ChatEngineService()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送对话消息"""
    fill(message_preview=(request.message or "")[:100])
    try:
        response = await chat_service.chat(
            conversation_id=request.conversation_id,
            user_message=request.message,
            image_paths=request.image_paths,
            file_paths=request.file_paths,
        )
        fill(conversation_id=response.conversation_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（SSE）

    逐行返回事件 data: {json}，事件类型：
    conversation_id（首事件）/ delta（文本增量）/ cards / done / error

    观测埋点（SDD §4.4）：TTFT/delta 节奏/CancelledError 中断捕获/finally 落盘。
    """
    async def event_gen():
        deltas: list = []
        t_start = time.time()
        t_first = None
        fill(message_preview=(request.message or "")[:100])
        try:
            async for evt in chat_service.stream_chat(
                conversation_id=request.conversation_id,
                user_message=request.message,
                image_paths=request.image_paths,
                file_paths=request.file_paths,
            ):
                if "conversation_id" in evt:
                    fill(conversation_id=evt["conversation_id"])
                if evt.get("delta"):
                    now = time.time()
                    if t_first is None:
                        t_first = now
                        fill(ttft_ms=round((t_first - t_start) * 1000, 1))
                    deltas.append(now)
                yield f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
        except asyncio.CancelledError:  # ★ 用户点 ⏹ 停止/断开连接（BaseException，except Exception 捕不到）
            fill(user_interrupted=True, status="interrupted",
                 waited_ms=round((time.time() - t_start) * 1000, 1))
            raise  # 必须 re-raise，保持取消传播（SDD D4）
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            fill(status="error", error=f"{type(e).__name__}: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            fill(stream=stream_metrics(deltas))
            write_request(get_context())  # 流式在此落盘（中间件豁免）

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ai-stream")
async def chat_ai_stream(request: ChatRequest):
    """AI SDK 5 UI Message Stream 协议端点（React 前端专用）

    复用 stream_chat，将自研事件映射为 UI Message Stream：
    start / data-conversation / text-start / text-delta / text-end /
    data-card / error / finish / [DONE]

    观测埋点与 /stream 同构（SDD §4.4 / M1 清单 #4）。
    """
    async def event_gen():
        def sse(obj):
            return f"data: {json.dumps(obj, ensure_ascii=False, default=str)}\n\n"

        deltas: list = []
        t_start = time.time()
        t_first = None
        fill(message_preview=(request.message or "")[:100])
        try:
            yield sse({"type": "start"})
            text_id, started = "t1", False
            async for evt in chat_service.stream_chat(
                conversation_id=request.conversation_id,
                user_message=request.message,
                image_paths=request.image_paths,
                file_paths=request.file_paths,
            ):
                if "conversation_id" in evt:
                    fill(conversation_id=evt["conversation_id"])
                    yield sse({"type": "data-conversation",
                               "data": {"conversation_id": evt["conversation_id"]}})
                if evt.get("delta"):
                    now = time.time()
                    if t_first is None:
                        t_first = now
                        fill(ttft_ms=round((t_first - t_start) * 1000, 1))
                    deltas.append(now)
                    if not started:
                        yield sse({"type": "text-start", "id": text_id})
                        started = True
                    yield sse({"type": "text-delta", "id": text_id, "delta": evt["delta"]})
                for card in evt.get("cards") or []:
                    yield sse({"type": "data-card", "data": card})
                if evt.get("error"):
                    yield sse({"type": "error", "errorText": evt["error"]})
            if started:
                yield sse({"type": "text-end", "id": text_id})
            yield sse({"type": "finish"})
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:  # ★ 用户点 ⏹ 停止（useChat stop() 断开连接）
            fill(user_interrupted=True, status="interrupted",
                 waited_ms=round((time.time() - t_start) * 1000, 1))
            raise
        except Exception as e:
            logger.error(f"AI流式对话失败: {e}")
            fill(status="error", error=f"{type(e).__name__}: {e}")
            yield sse({"type": "error", "errorText": str(e)})
        finally:
            fill(stream=stream_metrics(deltas))
            write_request(get_context())

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"x-vercel-ai-ui-message-stream": "v1",
                 "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class FeedbackRequest(BaseModel):
    """👍👎 反馈请求体（SDD §6.2，US-F1）"""
    rating: int                              # 1 | -1
    message_id: Optional[int] = None
    conversation_id: Optional[int] = None
    trace_id: Optional[str] = ""             # 关联原请求，-1 时触发 explicit_negative
    comment: Optional[str] = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """用户反馈（SDD §6.2）：rating=-1 落 rum.jsonl，回流采集按 trace_id
    合并出 rating=-1 → explicit_negative 规则进评审队列（US-B1）。

    本端点天然被中间件覆盖（path=/api/chat/feedback），无需单独埋点。
    """
    try:
        if req.rating not in (1, -1):
            raise HTTPException(status_code=400, detail="rating 只能为 1 或 -1")
        write_rum({"type": "feedback", "trace_id": req.trace_id or "",
                   "message_id": req.message_id, "conversation_id": req.conversation_id,
                   "rating": req.rating, "comment": (req.comment or "")[:200]})
        return {"ok": True, "rating": req.rating}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"反馈提交失败: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(limit: int = 50):
    """获取对话列表"""
    try:
        return chat_service.list_conversations(limit)
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int):
    """获取对话详情（含完整消息历史，供前端切换会话复原）"""
    try:
        conv = chat_service.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        # service 返回含 messages 但无 message_count，按长度派生回填
        conv["message_count"] = len(conv.get("messages") or [])
        return conv
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations", response_model=dict)
async def create_conversation(request: Optional[ConversationCreate] = None):
    """创建新对话"""
    try:
        title = request.title if request else None
        conv_id = chat_service.create_conversation(title)
        return {"id": conv_id, "message": "对话创建成功"}
    except Exception as e:
        logger.error(f"创建对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """删除对话"""
    try:
        success = chat_service.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="对话不存在")
        return {"message": "对话删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
