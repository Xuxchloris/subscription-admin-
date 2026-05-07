export type ApiError = {
  code: string;
  message: string;
  operation?: string | null;
  hermes_output?: string | null;
  suggested_checks: string[];
};

export type ApiResponse<T> = {
  success: boolean;
  data: T | null;
  error: ApiError | null;
};

export type LoginResult = {
  token?: string;
  access_token?: string;
  token_type?: string;
  username?: string | null;
};

export type ChangePasswordPayload = {
  current_password: string;
  new_password: string;
};

export type HermesHealth = {
  cli_available?: boolean;
  gateway_running?: boolean;
  cron_readable?: boolean;
  output_readable?: boolean;
  last_operation_result?: string | null;
  total_jobs?: number;
  active_jobs?: number;
  paused_jobs?: number;
  sync_problem_jobs?: number;
  checks?: Record<string, boolean | string | null>;
};

export type HermesJob = {
  id: string;
  name: string;
  task_name?: string;
  owner_label?: string;
  prompt: string;
  schedule: string;
  deliver: string;
  skills: string[];
  status: "active" | "paused" | "unknown";
  sync_status?: "synced" | "pending_confirmation" | "sync_error" | "last_operation_failed";
  last_run_result?: string | Record<string, unknown> | null;
  next_run_at?: string | null;
  notes?: string | null;
  latest_output?: string | null;
  content_id?: string;
  content_title?: string;
  content_template_id?: number | null;
  content_template_name?: string;
  delivery_label?: string;
  duration_days?: number | null;
  starts_at?: string | null;
  expires_at?: string | null;
  expired_at?: string | null;
  expiry_status?: string;
  seconds_remaining?: number | null;
};

export type JobPayload = {
  owner_label: string;
  task_name: string;
  prompt: string;
  schedule: string;
  deliver: string;
  skills: string[];
  notes?: string;
};

export type ContentDeliveryPayload = {
  schedule: string;
  deliver: string;
  label?: string;
};

export type ContentGroupPayload = {
  owner_label: string;
  title: string;
  prompt: string;
  skills: string[];
  notes?: string;
  content_template_id?: number | null;
  content_template_name?: string;
  duration_days?: number | null;
  deliveries: ContentDeliveryPayload[];
};

export type ContentDelivery = {
  job_id: string;
  label?: string;
  schedule: string;
  deliver: string;
  status: HermesJob["status"];
  next_run_at?: string | null;
  sync_status?: HermesJob["sync_status"];
  last_error?: string;
  last_run_result?: string | Record<string, unknown> | null;
  expires_at?: string | null;
  expired_at?: string | null;
  expiry_status?: string;
  seconds_remaining?: number | null;
};

export type ContentGroup = {
  content_id: string;
  title: string;
  owner_label: string;
  prompt: string;
  skills: string[];
  notes?: string | null;
  content_template_id?: number | null;
  content_template_name?: string;
  duration_days?: number | null;
  expires_at?: string | null;
  expiry_status?: string;
  seconds_remaining?: number | null;
  deliveries: ContentDelivery[];
};

export type ContentTemplate = {
  id: number;
  name: string;
  prompt: string;
  skills: string[];
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ContentTemplatePayload = {
  name: string;
  prompt: string;
  skills: string[];
  notes?: string;
};

export type JobRun = {
  id?: string;
  file_name?: string;
  path?: string;
  size_bytes?: number;
  modified_at?: number | string | null;
  started_at?: string | null;
  finished_at?: string | null;
  status?: string;
  output?: string | null;
  error?: string | null;
  content?: string | null;
};

export type AuditEvent = {
  id: string | number;
  timestamp: string;
  operation_type: string;
  target_job_id?: string | null;
  owner_label?: string | null;
  request_summary?: string | null;
  hermes_command_category?: string | null;
  result_status: string;
  error_message?: string | null;
};

export type Customer = {
  id: number;
  name: string;
  contact: string;
  status: string;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CustomerPayload = {
  name: string;
  contact?: string;
  status?: string;
  notes?: string;
};

export type Subscription = {
  id: number;
  customer_id: number;
  customer_name: string;
  content_template_id?: number | null;
  content_template_name?: string;
  deliver_channel: string;
  deliver_address: string;
  frequency: string;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  status: string;
  expiry_status: string;
  days_remaining?: number | null;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SubscriptionPayload = {
  customer_id: number;
  content_template_id?: number | null;
  deliver_channel: string;
  deliver_address?: string;
  frequency?: string;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  status?: string;
  notes?: string;
};

export type SubscriptionFilters = {
  search?: string;
  status?: string;
  customer_id?: number | null;
  content_template_id?: number | null;
  deliver_channel?: string;
};

export type SubscriptionSummary = {
  customer_count: number;
  active_subscription_count: number;
  expiring_soon_count: number;
  expired_subscription_count: number;
  recent_subscriptions: Subscription[];
};
