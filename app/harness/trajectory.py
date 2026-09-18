"""轨迹记录模块 - 完整事件轨迹记录，支持审计和回放"""
import json
from typing import List, Dict
from datetime import datetime
from pathlib import Path
from loguru import logger


class TrajectoryRecorder:
    """完整事件轨迹记录器"""
    
    def __init__(self, storage_path: str = "./data/trajectories"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._buffers: Dict[str, List[Dict]] = {}
        logger.info(f"轨迹记录器初始化，存储路径: {self.storage_path}")
    
    def record_event(self, session_id: str, event: Dict):
        """记录单个事件"""
        if session_id not in self._buffers:
            self._buffers[session_id] = []
        
        event["id"] = len(self._buffers[session_id]) + 1
        if "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()
        
        self._buffers[session_id].append(event)
        logger.debug(f"记录事件: session={session_id}, type={event.get('type')}, id={event['id']}")
        
        # 每10个事件持久化一次
        if len(self._buffers[session_id]) % 10 == 0:
            self.flush(session_id)
    
    def flush(self, session_id: str):
        """持久化到文件"""
        if session_id in self._buffers and self._buffers[session_id]:
            file_path = self.storage_path / f"{session_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self._buffers[session_id], f, ensure_ascii=False, indent=2)
            logger.debug(f"轨迹持久化: {file_path}, 事件数: {len(self._buffers[session_id])}")
    
    def load_trajectory(self, session_id: str) -> List[Dict]:
        """加载完整轨迹（用于回放）"""
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                events = json.load(f)
                logger.info(f"加载轨迹: {session_id}, 事件数: {len(events)}")
                return events
        
        # 从缓冲区获取
        events = self._buffers.get(session_id, [])
        logger.info(f"从缓冲区获取轨迹: {session_id}, 事件数: {len(events)}")
        return events
    
    def replay(self, session_id: str) -> str:
        """回放轨迹（调试用），返回格式化字符串"""
        events = self.load_trajectory(session_id)
        if not events:
            return f"会话 {session_id} 无轨迹记录"
        
        output = []
        output.append(f"=== 会话轨迹回放: {session_id} ===")
        output.append(f"总事件数: {len(events)}")
        output.append("-" * 50)
        
        for event in events:
            timestamp = event.get("timestamp", "N/A")
            event_type = event.get("type", "unknown")
            
            if event_type == "task_start":
                output.append(f"[{timestamp}] 🚀 任务开始: {event.get('task', '')}")
            elif event_type == "model_output":
                content = event.get("content", "")[:100]
                output.append(f"[{timestamp}] 🤖 模型输出: {content}...")
                if event.get("tool_calls"):
                    for tc in event["tool_calls"]:
                        output.append(f"   └─ 调用工具: {tc.get('name')}")
            elif event_type == "tool_execution":
                tool_name = event.get("tool_name", "")
                success = event.get("result", {}).get("success", False)
                status = "✅" if success else "❌"
                output.append(f"[{timestamp}] {status} 工具执行: {tool_name}")
            elif event_type == "error":
                output.append(f"[{timestamp}] ❌ 错误: {event.get('error', '')}")
            elif event_type == "task_completed":
                output.append(f"[{timestamp}] 🎉 任务完成，总轮次: {event.get('total_turns', 0)}")
            else:
                output.append(f"[{timestamp}] {event_type}: {str(event)[:100]}")
        
        result = "\n".join(output)
        logger.info(f"轨迹回放完成: {session_id}")
        return result
    
    def get_last_state(self, session_id: str) -> Dict:
        """获取最后状态（用于断点恢复）"""
        events = self.load_trajectory(session_id)
        if not events:
            return {}
        return self._rebuild_state(events)
    
    def _rebuild_state(self, events: List[Dict]) -> Dict:
        """从事件流重建状态"""
        state = {
            "task": None,
            "context": [],
            "tool_results": [],
            "completed": False
        }
        for event in events:
            event_type = event.get("type")
            if event_type == "task_start":
                state["task"] = event.get("task")
            elif event_type == "model_output":
                state["context"].append(event)
            elif event_type == "tool_execution":
                state["tool_results"].append(event)
            elif event_type == "task_completed":
                state["completed"] = True
        return state
    
    def clear_session(self, session_id: str):
        """清除会话轨迹"""
        if session_id in self._buffers:
            del self._buffers[session_id]
        
        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"清除会话轨迹: {session_id}")
    
    def list_sessions(self) -> List[str]:
        """列出所有有轨迹的会话"""
        sessions = set(self._buffers.keys())
        
        # 从文件系统加载
        for file in self.storage_path.glob("*.json"):
            sessions.add(file.stem)
        
        return list(sessions)
