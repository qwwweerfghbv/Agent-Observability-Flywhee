"""工具管道模块 - 统一工具注册 + 执行前拦截"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class RiskLevel(Enum):
    """工具风险等级"""
    LOW = "low"              # 只读操作
    MEDIUM = "medium"        # 写本地文件
    HIGH = "high"            # 调用外部API
    CRITICAL = "critical"    # 删除/发送操作


@dataclass
class ToolPermission:
    """工具权限定义"""
    name: str
    risk_level: RiskLevel
    require_approval: bool = False      # 是否需要人工审批
    allowed_in_sandbox: bool = True     # 是否允许在沙箱执行
    max_calls_per_session: int = 100    # 单会话最大调用次数


class ToolRegistry:
    """统一工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._permissions: Dict[str, ToolPermission] = {}
        self._call_counts: Dict[str, int] = {}
    
    def register(self, tool, permission: ToolPermission):
        """注册工具及其权限"""
        self._tools[tool.name] = tool
        self._permissions[tool.name] = permission
        self._call_counts[tool.name] = 0
        logger.info(f"注册工具: {tool.name} (风险等级: {permission.risk_level.value})")
    
    def get(self, name: str):
        """获取工具"""
        return self._tools.get(name)
    
    def get_permission(self, name: str) -> Optional[ToolPermission]:
        """获取工具权限"""
        return self._permissions.get(name)
    
    def list_tools(self) -> list:
        """列出所有已注册工具"""
        return list(self._tools.keys())
    
    def get_call_count(self, name: str) -> int:
        """获取工具调用次数"""
        return self._call_counts.get(name, 0)


class ToolPipeline:
    """工具执行管道（带完整拦截链）"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
    
    def execute(self, tool_name: str, arguments: dict, session_id: str = "default") -> dict:
        """执行工具（带完整拦截链）"""
        
        logger.info(f"工具管道: 执行工具 {tool_name}, 会话: {session_id}")
        
        # Step 1: 查找工具
        tool = self.registry.get(tool_name)
        if not tool:
            logger.warning(f"工具 {tool_name} 不存在")
            return {"success": False, "error": f"工具 {tool_name} 不存在"}
        
        # Step 2: 权限检查
        permission = self.registry.get_permission(tool_name)
        if not permission:
            logger.warning(f"工具 {tool_name} 未注册权限")
            return {"success": False, "error": f"工具 {tool_name} 未注册权限"}
        
        # Step 3: 调用频率检查
        current_count = self.registry.get_call_count(tool_name)
        if current_count >= permission.max_calls_per_session:
            logger.warning(f"工具 {tool_name} 调用次数超限: {current_count}/{permission.max_calls_per_session}")
            return {"success": False, "error": f"工具 {tool_name} 调用次数超限"}
        
        # Step 4: 参数校验（JSON Schema）
        validation_result = self._validate_arguments(tool, arguments)
        if not validation_result["valid"]:
            logger.warning(f"工具 {tool_name} 参数校验失败: {validation_result['error']}")
            return {"success": False, "error": f"参数校验失败: {validation_result['error']}"}
        
        # Step 5: 风险评级与审批（骨架阶段简化处理）
        if permission.require_approval:
            logger.info(f"工具 {tool_name} 需要审批，骨架阶段自动通过")
            # TODO: 实现人工审批流程
        
        # Step 6: 执行工具
        import time as _time
        _start = _time.time()
        try:
            result = tool.run(**arguments)
            
            # 更新调用计数
            self.registry._call_counts[tool_name] = current_count + 1
            
            logger.info(f"工具 {tool_name} 执行成功")
            self._observe_tool(tool_name, arguments, True, _start)
            return {"success": True, "data": result}
            
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {str(e)}")
            self._observe_tool(tool_name, arguments, False, _start)
            return {"success": False, "error": f"工具执行失败: {str(e)}"}

    @staticmethod
    def _observe_tool(tool_name: str, arguments: dict, success: bool, start: float) -> None:
        """L4 工具管道埋点（SDD §4.5 P1）：记录 tool span（对齐 tool_execution 事件）。静默降级。"""
        try:
            import time
            import hashlib
            import json
            from app.observability.context import add_span
            digest = hashlib.md5(
                json.dumps(arguments, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:8]
            add_span("tool", tool_name=tool_name, success=success,
                     duration_ms=round((time.time() - start) * 1000, 1), args_digest=digest)
        except Exception:
            pass
    
    def _validate_arguments(self, tool, arguments: dict) -> dict:
        """参数校验"""
        try:
            # 使用Pydantic校验（如果工具有input_schema）
            if hasattr(tool, 'input_schema'):
                tool.input_schema(**arguments)
            return {"valid": True}
        except Exception as e:
            return {"valid": False, "error": str(e)}
