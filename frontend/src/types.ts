
export type DashboardGroup =
  | "needs_attention"
  | "important_updates"
  | "low_priority"
  | "cleanup";

export type CleanupAction =
  | "keep"
  | "archive"
  | "unsubscribe";

export interface CleanupRecommendation {
  action: CleanupAction;
  reason: string;
  approval_required: boolean;
  unsubscribe_available: boolean;
}

export interface ConversationCard {
  thread_id: string;
  message_ids: string[];
  message_count: number;
  subject: string;
  senders: string[];
  latest_received_at_ms: number;
  priority: string;
  category: string;
  dashboard_group: DashboardGroup;
  summary: string;
  action_status: string;
  requires_action: boolean;
  suggested_action: string | null;
  action_reason: string;
  needs_review: boolean;
  gmail_url: string;
  cleanup: CleanupRecommendation | null;
}

export interface DashboardResponse {
  last_analyzed_at: string | null;
  cards: ConversationCard[];
}

export interface AnalyzeRequest {
  hours: number;
  max_threads: number;
  max_workers: number;
  user_priorities: string;
}

export interface AnalyzeResponse extends DashboardResponse {
  status: string;
  messages_processed: number;
  conversation_count: number;
}

export interface HealthResponse {
  backend: string;
  ollama_available: boolean;
  scan_running: boolean;
}
