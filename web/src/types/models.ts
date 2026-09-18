import type { UIMessage } from 'ai';

// ============================================================
// 卡片数据类型（严格对齐后端 chat_engine / models.conversation）
// ============================================================

/** score_card：岗位评分（dimensions 为 5 维，取值 0-100） */
export interface ScoreCardData {
  total_score: number;
  score_level: string; // A/B/C/D
  dimensions: {
    skill: number;
    experience: number;
    salary: number;
    stability: number;
    growth: number;
  };
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  stability_signals?: Record<string, unknown>;
  ai_replacement_risk?: number; // 0-100
}

/** diff_card 单条修改项 */
export interface DiffItem {
  section: string;
  before: string;
  after: string;
  reason: string;
  confirmed?: boolean | null;
}

/** diff_card：简历修改对比 */
export interface DiffCardData {
  items: DiffItem[];
  total_changes: number;
  confirmed_count: number;
}

/** question_card 单道题 */
export interface InterviewQuestion {
  question: string;
  skill: string;
  difficulty: string;
  reference_answer: string;
}

/** question_card：面试题 */
export interface QuestionCardData {
  interview_type: string; // technical/behavioral/hr
  questions: InterviewQuestion[];
}

/** progress_card：投递进度 */
export interface ProgressCardData {
  daily_target: number;
  applied_today: number;
  remaining: number;
  encouragement: string;
}

/** recommend_card：岗位推荐 */
export interface RecommendCardData {
  jobs: Array<{ id?: number; title: string; company: string; salary: string }>;
}

/** image_card / file_card：附件回显 */
export interface AttachmentCardData {
  url: string;
  index: number;
}

/** 判别联合：按 type 收窄 data，CardRenderer 分发时类型安全 */
export type CardPayload =
  | { type: 'score_card'; data: ScoreCardData }
  | { type: 'diff_card'; data: DiffCardData }
  | { type: 'question_card'; data: QuestionCardData }
  | { type: 'progress_card'; data: ProgressCardData }
  | { type: 'recommend_card'; data: RecommendCardData }
  | { type: 'image_card'; data: AttachmentCardData }
  | { type: 'file_card'; data: AttachmentCardData };

// ============================================================
// AI SDK UIMessage（自定义 data parts）
// ============================================================

/** data-card 承载富卡片，data-conversation 承载会话ID（副作用回收） */
export type JobAgentUIMessage = UIMessage<
  unknown,
  {
    card: CardPayload;
    conversation: { conversation_id: number };
  }
>;

// ============================================================
// 会话（对齐 ConversationResponse / ConversationDetail）
// ============================================================

/** GET /api/chat/conversations 列表项 */
export interface ConversationSummary {
  id: number;
  title: string;
  message_count: number;
  context_job_id?: number | null;
  context_resume_id?: number | null;
  created_at: string;
  updated_at: string;
}

/** 后端存储的历史消息（user 无 cards，assistant 含 cards） */
export interface HistoryMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  cards?: CardPayload[];
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

/** GET /api/chat/conversations/{id} 详情（含 messages，供切换会话复原） */
export interface ConversationDetail extends ConversationSummary {
  messages: HistoryMessage[];
}

// ============================================================
// 上传（对齐 /api/upload/images、/api/upload/files）
// ============================================================

export interface UploadedImage {
  filename: string;
  saved_name: string;
  url: string; // /api/upload/images/{name}
  size: number;
}

export interface UploadImagesResponse {
  images: UploadedImage[];
  count: number;
}

export interface UploadedFile {
  filename: string;
  saved_name: string;
  url: string; // /api/upload/files/{name}
  size: number;
  content_type: string;
}

export interface UploadFilesResponse {
  files: UploadedFile[];
  count: number;
}

// ============================================================
// 工作台 / 设置（P3，对齐 app/models/settings.py、application.py）
// ============================================================

/** GET /api/settings/belief/today：今日信念 */
export interface DailyBelief {
  content: string;
  category: string; // persist/confidence/growth/expression
}

/** GET /api/settings/job-seeking-stats：求职统计 */
export interface JobSeekingStats {
  days_count: number;
  total_applied: number;
  interview_count: number;
  offer_count: number;
}

/** GET /api/application/today/progress：今日投递进度 */
export interface DailyProgress {
  daily_target: number;
  applied_today: number;
  valid_applied: number;
  remaining: number;
  encouragement: string;
}

/** GET /api/settings：用户偏好 */
export interface UserPreferences {
  target_city: string;
  expected_salary_min: number;
  target_positions: string[];
  excluded_keywords: string[];
  daily_apply_target: number;
  job_start_date?: string | null; // ISO date 'YYYY-MM-DD'
  llm_provider: string;
  llm_model: string;
}

/** PUT /api/settings 请求体（全部可选，仅提交变更字段） */
export type SettingsUpdate = Partial<UserPreferences>;

// ============================================================
// 岗位 / 简历 / 投递（P3，对齐 app/api/job.py、resume.py、application.py）
// ============================================================

/** GET /api/job/ 列表项 */
export interface JobSummary {
  id: number;
  title: string;
  company: string;
  location: string;
  salary: string;
  created_at: string | null;
}

export interface JobListResponse {
  total: number;
  jobs: JobSummary[];
}

/** 岗位详情 data_json（JobData，宽松定义：后端 LLM 解析字段可能缺省） */
export interface JobDataPayload {
  title: string;
  company: string;
  location?: string;
  salary_min?: number | null;
  salary_max?: number | null;
  years_required?: number | null;
  education_required?: string;
  requirements?: Array<{ skill: string; importance?: string }>;
  responsibilities?: string[];
  benefits?: string[];
  industry?: string;
}

/** GET /api/job/{id} */
export interface JobDetail {
  id: number;
  data: JobDataPayload;
  created_at: string;
}

/** GET /api/resume/ 列表项 */
export interface ResumeSummary {
  id: number;
  name: string;
  location: string;
  years_of_experience: number;
  created_at: string | null;
}

export interface ResumeListResponse {
  total: number;
  resumes: ResumeSummary[];
}

/** 简历详情 data（ResumeData，对齐 app/models/resume.py） */
export interface ResumeDataPayload {
  name: string;
  phone?: string;
  email?: string;
  location?: string;
  years_of_experience?: number;
  educations?: Array<{ school: string; degree: string; major: string }>;
  work_experiences?: Array<{
    company: string;
    position: string;
    start_date?: string;
    end_date?: string;
    description?: string;
    achievements?: string[];
  }>;
  projects?: Array<{
    name: string;
    role?: string;
    description?: string;
    technologies?: string[];
    achievements?: string[];
  }>;
  skills?: Array<{ name: string; level?: string; category?: string }>;
  summary?: string;
}

/** GET /api/resume/{id} */
export interface ResumeDetail {
  id: number;
  data: ResumeDataPayload;
  created_at: string;
}

/** POST /api/resume/upload 响应 */
export interface ResumeUploadResponse {
  id: number;
  name: string;
  skills_count: number;
  message: string;
}

/** 投递状态（ApplicationStatus 枚举） */
export type ApplicationStatus =
  | 'pending'
  | 'applied'
  | 'screening'
  | 'interview'
  | 'offer'
  | 'rejected'
  | 'inappropriate';

/** GET /api/application 列表项 */
export interface ApplicationRecord {
  id: number;
  job_id: number;
  resume_id: number | null;
  apply_date: string | null;
  platform: string;
  status: ApplicationStatus;
  notes: string;
  created_at: string;
  updated_at: string;
}

/** POST /api/application 请求体 */
export interface ApplicationCreate {
  job_id: number;
  resume_id?: number | null;
  apply_date?: string | null;
  platform?: string;
  status?: ApplicationStatus;
  notes?: string;
}

/** GET /api/application/stats */
export interface ApplicationStats {
  today_count: number;
  week_count: number;
  interview_count: number;
  offer_count: number;
  pass_rate: number;
  total_applied: number;
}
