"""Prompt模板管理模块

统一管理所有LLM Prompt模板，支持变量替换和版本迭代。
"""
from typing import Dict, Optional
from string import Template


# ============================================================
# 系统级Prompt
# ============================================================

SYSTEM_PROMPT = """你是一个专业的求职助手Agent。

## 你的能力
- 解析简历和JD文本，提取结构化信息
- 评估岗位与简历的匹配度，给出综合评分
- 根据目标JD优化简历内容（不编造经历）
- 生成针对性面试题（技术面+行为面+HR面）
- 模拟面试对话，提供回答质量反馈

## 工作规则
1. 先理解用户需求，再选择合适工具
2. 使用工具时说明原因
3. 不确定时主动询问用户
4. 每次回复保持简洁有条理
5. 涉及数据时给出具体数字

## 输出格式
- 使用结构化JSON输出（当需要解析时）
- 普通回复使用Markdown格式
- 评分结果包含各维度分数和综合建议

## 限制
- 不要编造用户没有的经历
- 不要编造公司不存在的信息
- 工具调用失败时如实告知
- 不主动建议用户跳槽或离职
- 不替用户做最终决策
"""


# ============================================================
# 简历相关Prompt
# ============================================================

RESUME_PARSE_PROMPT = """请解析以下简历文本，提取结构化信息。

## 简历原文
{resume_text}

## 输出格式
```json
{{
    "name": "姓名",
    "phone": "手机号",
    "email": "邮箱",
    "education": [
        {{
            "school": "学校",
            "major": "专业",
            "degree": "学历",
            "start_date": "开始时间",
            "end_date": "结束时间"
        }}
    ],
    "work_experience": [
        {{
            "company": "公司",
            "position": "职位",
            "start_date": "开始时间",
            "end_date": "结束时间",
            "description": "工作内容",
            "achievements": ["成果1", "成果2"]
        }}
    ],
    "project_experience": [
        {{
            "name": "项目名",
            "role": "角色",
            "tech_stack": ["技术1", "技术2"],
            "description": "项目描述",
            "achievements": ["成果1"]
        }}
    ],
    "skills": ["技能1", "技能2"],
    "self_evaluation": "自我评价",
    "certificates": ["证书1"],
    "languages": ["语言1"]
}}
```

## 要求
- 严格按照上述JSON格式输出
- 如果某个字段在简历中找不到，填null或空数组
- 不要编造简历中没有的信息
"""

RESUME_OPTIMIZE_PROMPT = """请根据以下JD优化简历内容。

## 目标JD
{jd_text}

## 原始简历
{resume_text}

## 优化要求
1. 提取JD中的核心关键词（最多10个）
2. 调整简历项目顺序，将最相关的内容放前面
3. 优化项目描述，突出与JD匹配的成果
4. 生成针对性的自我评价（3-5句话）

## 严格限制
- 不能编造用户没有的经历
- 不能虚构数据或成果
- 只能优化表达方式，不能改变事实
- 保留所有原始信息，只做增补和重排

## 输出格式
```json
{{
    "keywords": ["关键词1", "关键词2"],
    "optimized_sections": {{
        "work_experience": "优化后的工作经历",
        "project_experience": "优化后的项目经历",
        "self_evaluation": "优化后的自我评价"
    }},
    "changes_summary": ["改动说明1", "改动说明2"],
    "match_score": 85
}}
```
"""


# ============================================================
# JD相关Prompt
# ============================================================

JD_PARSE_PROMPT = """请解析以下JD文本，提取结构化信息。

## JD原文
{jd_text}

## 输出格式
```json
{{
    "company_name": "公司名称",
    "job_title": "岗位名称",
    "required_skills": ["必须技能1", "必须技能2"],
    "preferred_skills": ["加分技能1", "加分技能2"],
    "experience_years": 3,
    "education": "学历要求",
    "salary_min": 25000,
    "salary_max": 40000,
    "city": "工作城市",
    "job_description": "岗位描述摘要",
    "company_info": {{
        "industry": "行业",
        "scale": "规模",
        "funding_stage": "融资阶段"
    }}
}}
```

## 要求
- 严格按照上述JSON格式输出
- 薪资统一换算为月薪（元）
- 如果JD中未明确标注，填null
- 经验年限填数字（如"3-5年"填3）
"""


# ============================================================
# 面试相关Prompt
# ============================================================

QUESTION_GENERATE_PROMPT = """请根据以下岗位信息生成{question_type}面试题。

## 岗位信息
- 岗位名称：{job_title}
- 技能要求：{required_skills}
- 岗位描述：{job_description}

## 候选人背景
{candidate_background}

## 题目类型说明
{type_description}

## 输出要求
生成{num_questions}道面试题，每题包含：
- 题目（清晰具体）
- 考察点（这道题考什么）
- 参考答案要点（关键得分点）
- 难度（简单/中等/困难）

## 输出格式
```json
{{
    "questions": [
        {{
            "question": "题目内容",
            "focus": "考察点",
            "answer_key": "参考答案要点",
            "difficulty": "中等"
        }}
    ]
}}
```
"""

MOCK_INTERVIEW_PROMPT = """你正在进行一场模拟面试。

## 面试背景
- 岗位：{job_title}
- 面试类型：{interview_type}
- 当前题目：{current_question}

## 候选人回答
{candidate_answer}

## 评估要求
请从以下维度评估回答质量：
1. 完整性（是否覆盖了关键点）
2. 准确性（技术内容是否正确）
3. 表达力（是否清晰有条理）
4. 相关性（是否紧扣题目）

## 输出格式
```json
{{
    "score": 75,
    "feedback": {{
        "strengths": ["优点1", "优点2"],
        "weaknesses": ["不足1", "不足2"],
        "improvements": ["改进建议1", "改进建议2"]
    }},
    "reference_answer": "参考答案"
}}
```
"""


# ============================================================
# 规划相关Prompt
# ============================================================

TASK_PLANNING_PROMPT = """用户提出了一个求职相关的需求，请将其分解为可执行的步骤。

## 用户需求
{user_task}

## 可用工具
{available_tools}

## 输出要求
将任务分解为有序步骤，每步说明：
- 使用什么工具
- 输入是什么
- 预期输出是什么

## 输出格式
```json
{{
    "task_summary": "任务摘要",
    "steps": [
        {{
            "step": 1,
            "action": "执行的动作",
            "tool": "使用的工具名",
            "input": "输入说明",
            "expected_output": "预期输出"
        }}
    ],
    "estimated_turns": 3
}}
```
"""


# ============================================================
# Reflection相关Prompt
# ============================================================

REFLECTION_PROMPT = """请检查以下Agent执行结果的质量。

## 原始任务
{original_task}

## Agent执行结果
{agent_output}

## 执行轨迹摘要
{trajectory_summary}

## 检查维度
1. 结果是否完整回答了用户的问题？
2. 是否有编造或虚假信息？
3. 工具调用是否合理？
4. 输出格式是否符合要求？

## 输出格式
```json
{{
    "quality_score": 85,
    "is_complete": true,
    "issues": ["问题1", "问题2"],
    "suggestions": ["改进建议1"],
    "needs_retry": false
}}
```
"""


# ============================================================
# Prompt管理器
# ============================================================

class PromptManager:
    """Prompt模板管理器"""
    
    _templates: Dict[str, str] = {
        "system": SYSTEM_PROMPT,
        "resume_parse": RESUME_PARSE_PROMPT,
        "resume_optimize": RESUME_OPTIMIZE_PROMPT,
        "jd_parse": JD_PARSE_PROMPT,
        "question_generate": QUESTION_GENERATE_PROMPT,
        "mock_interview": MOCK_INTERVIEW_PROMPT,
        "task_planning": TASK_PLANNING_PROMPT,
        "reflection": REFLECTION_PROMPT,
    }
    
    @classmethod
    def get(cls, name: str, **kwargs) -> str:
        """获取渲染后的Prompt"""
        template = cls._templates.get(name)
        if template is None:
            raise ValueError(f"Prompt模板不存在: {name}，可选: {list(cls._templates.keys())}")
        
        if kwargs:
            return template.format(**kwargs)
        return template
    
    @classmethod
    def register(cls, name: str, template: str):
        """注册新的Prompt模板"""
        cls._templates[name] = template
    
    @classmethod
    def list_templates(cls) -> list:
        """列出所有模板名称"""
        return list(cls._templates.keys())
    
    @classmethod
    def get_system_prompt(cls) -> str:
        """获取系统Prompt"""
        return cls._templates["system"]
