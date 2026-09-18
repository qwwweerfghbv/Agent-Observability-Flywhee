// 可观测平台类型契约（SDD §5.10.3）——字段与后端 snake_case 完全一致。
// schema 演进"只增不改"，新增字段用可选吸收。

/** 七层状态灯色（后端 /summary layers[].status） */
export type LayerStatus = 'green' | 'warning' | 'critical' | 'unknown';

/** SLO 单条判定状态（后端 /slo slo[].state） */
export type SloState = 'ok' | 'warning' | 'critical' | 'no_data';

/** 告警级别 */
export type AlertLevel = 'critical' | 'warning' | 'ok';

export type ObsWindow = '1h' | '24h' | '7d' | '30d';

export interface LayerLight {
  status: LayerStatus;
  note?: string;
  [k: string]: unknown;
}

export interface SummaryResponse {
  health_score: number;
  window: string;
  request_count?: number;
  layers: Record<'L1' | 'L2' | 'L3' | 'L4' | 'L5' | 'L6' | 'L7', LayerLight>;
  flywheel: {
    badcase_pending: number;
    merged_this_week: number;
    prod_case_pass_rate: number | null;
  };
  alerts: Array<{ level: AlertLevel | string; layer: string; rule: string; msg: string }>;
  error?: string;
}

export interface SloItem {
  layer: string;
  metric: string;
  op: string;
  value: number;
  actual: number | null;
  state: SloState;
  level?: string;
}

export interface SloResponse {
  window: string;
  slo: SloItem[];
  critical_violations: SloItem[];
  warning_violations: SloItem[];
  health_score: number;
  error?: string;
}

export interface MetricsAggregate {
  request_count: number;
  status_dist: Record<string, number>;
  intent_dist: Record<string, number>;
  model_dist: Record<string, number>;
  request_error_rate: number | null;
  degraded_rate: number | null;
  interrupted_rate: number | null;
  llm_error_rate: number | null;
  ttft_p50_ms: number | null;
  ttft_p95_ms: number | null;
  duration_p50_ms: number | null;
  duration_p95_ms: number | null;
  stream_gap_median_ms: number | null;
  tokens_total: number;
  // 记忆观测指标（后端 monitor.aggregate）
  memory_error_count?: number;
  memory_warn_count?: number;
  memory_error_rate?: number | null;
  memory_warn_rate?: number | null;
  memory_flag_dist?: Record<string, number>;
  session_persist_fail_count?: number;
  memory_trim_events?: number;
}

export interface MetricsResponse {
  window: string;
  aggregate: MetricsAggregate;
  infra_latest: Record<string, unknown>;
  error?: string;
}

export interface TraceListItem {
  trace_id: string;
  ts: string;
  path: string;
  method: string;
  intent: string | null;
  status: string;
  duration_ms: number | null;
  ttft_ms: number | null;
  degraded: boolean;
  user_interrupted: boolean;
  security_hit?: boolean;
  message_preview?: string;
}

export interface TraceSpan {
  span: string;
  ts?: number;
  [k: string]: unknown;
}

export interface TraceDetail {
  trace_id: string;
  path: string;
  method: string;
  status: string;
  ts: string;
  timing: {
    preprocess_ms: number | null;
    ttft_ms: number | null;
    stream_span_ms: number | null;
    llm_duration_ms: number | null;
    total_ms: number | null;
  };
  stream: { delta_count: number | null; gap_median_ms: number | null; delta_gaps?: number[] };
  intent: { name: string | null; confidence: number | null; ambiguous: boolean | null };
  llm: {
    model: string | null;
    tokens: { prompt: number; completion: number; total: number } | null;
    degraded: boolean;
    llm_error: string | null;
  };
  quality: {
    card_count: number | null;
    empty_reply: boolean | null;
    security_hit: boolean | null;
    quality_flags: string[] | null;
    scores?: Record<string, number> | null;
    judge_reason?: string | null;
    judge_model?: string | null;
  };
  version: Record<string, string> | null;
  memory?: {
    flags: string[] | null;
    msg_persisted: boolean | null;
    spans: TraceSpan[];
  };
  spans: TraceSpan[];
  logs: string[];
  error?: string;
}

/** 链路检索列表响应（GET /traces） */
export interface TraceListResponse {
  window: string;
  count: number;
  returned: number;
  items: TraceListItem[];
  error?: string;
}

export interface QualityResponse {
  window: string;
  total_records: number;
  sampled_scored: number;
  red_line_hits: number;
  injection_hits: number;
  sensitive_hits: number;
  flag_dist: Record<string, number>;
  dimension_avg: Record<string, number>;
  error?: string;
}

export interface BadCaseDraft {
  id: string;
  rule: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  layer: string;
  trace_id: string;
  message_preview: string;
  ts: string;
  occurrences?: number;
  metrics: { duration_ms?: number | null; ttft_ms?: number | null; gap_median_ms?: number | null };
  draft: { input: string; module: string; priority: string; tags: string[]; expected: string };
  pii_hits: string[];
  status?: string;
}

export interface BadCaseListResponse {
  status: string;
  count: number;
  by_severity: Record<string, number>;
  items: BadCaseDraft[];
  collect_stats?: Record<string, unknown> | null;
  error?: string;
}

export interface EvalRunSummary {
  run_id: string;
  timestamp: string;
  agent_version: string;
  total_cases: number;
  pass_rate: number;
  gate_passed: boolean;
}

export interface FlakeCase {
  case_id: string;
  runs: number;
  pass_count: number;
  pass_rate: number;
}

export interface ReportsResponse {
  count: number;
  runs: EvalRunSummary[];
  latest_comparison: Record<string, unknown> | null;
  flake: { flake_cases: FlakeCase[]; count: number } | null;
  run_ids: string[];
  error?: string;
}

export interface EvalSpan {
  span: string;
  run_id: string;
  span_id?: string | null;
  parent?: string | null;
  end_ts?: number;
  attrs: Record<string, unknown>;
}

export interface EvalTraceResponse {
  run_id: string;
  source: string;
  progress: { done: number; total: number; current: string | null; live: boolean };
  eval_run: Record<string, unknown>;
  spans: EvalSpan[];
  error?: string;
}

export interface WeeklyResponse {
  week: string;
  eval_runs: number;
  latest_run: EvalRunSummary | null;
  latest_pass_rate: number | null;
  badcase_pending: number;
  badcase_merged: number;
  badcase_discarded: number;
  pending_by_severity: Record<string, number>;
  generated_at: string;
  error?: string;
}

export interface EventsResponse {
  count: number;
  items: Array<Record<string, unknown>>;
  error?: string;
}

/** RUM 上报事件（L6，SDD §4.7） */
export type RumEvent =
  | { type: 'js_error'; message: string; stack_summary?: string }
  | { type: 'card_render_fail'; card_type: string; message?: string }
  | { type: 'feedback'; rating: number; comment?: string; trace_id?: string; message_id?: number };
