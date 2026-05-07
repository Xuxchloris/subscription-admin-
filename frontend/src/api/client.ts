import type {
  ApiError,
  ApiResponse,
  AuditEvent,
  ChangePasswordPayload,
  ContentGroup,
  ContentGroupPayload,
  ContentTemplate,
  ContentTemplatePayload,
  Customer,
  CustomerPayload,
  HermesHealth,
  HermesJob,
  JobPayload,
  JobRun,
  LoginResult,
  Subscription,
  SubscriptionFilters,
  SubscriptionPayload,
  SubscriptionSummary
} from "./types";

const TOKEN_KEY = "hermes_admin_token";

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, {
    ...options,
    headers
  });

  const text = await response.text();
  if (!text.trim()) {
    if (response.ok) {
      return null as T;
    }
    throw {
      code: "API_ERROR",
      message: "The Hermes Admin API returned an unreadable response.",
      suggested_checks: ["Confirm the FastAPI backend is returning JSON."]
    } satisfies ApiError;
  }

  let body: ApiResponse<T>;
  try {
    body = JSON.parse(text) as ApiResponse<T>;
  } catch {
    throw {
      code: "API_ERROR",
      message: "The Hermes Admin API returned an unreadable response.",
      suggested_checks: ["Confirm the FastAPI backend is returning JSON."]
    } satisfies ApiError;
  }

  if (!response.ok || !body.success) {
    if (response.status === 401) {
      clearToken();
    }
    throw (
      body.error ?? {
        code: "API_ERROR",
        message: "Request failed.",
        suggested_checks: []
      }
    );
  }

  return body.data as T;
}

export async function login(username: string, password: string) {
  const result = await apiRequest<LoginResult>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  const token = result.access_token ?? result.token;
  if (!token) {
    throw {
      code: "AUTH_RESPONSE_INVALID",
      message: "Login succeeded but the API did not return an access token.",
      operation: "login",
      suggested_checks: ["Confirm the FastAPI auth response includes access_token."]
    } satisfies ApiError;
  }
  setToken(token);
  return { ...result, token };
}

export async function logout() {
  try {
    await apiRequest<null>("/api/auth/logout", { method: "POST" });
  } finally {
    clearToken();
  }
}

export function changePassword(payload: ChangePasswordPayload) {
  return apiRequest<{ status: string }>("/api/auth/password", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getHermesHealth() {
  return apiRequest<unknown>("/api/health/hermes").then(normalizeHealth);
}

export function listJobs() {
  return apiRequest<HermesJob[]>("/api/jobs").then((jobs) => jobs.map(normalizeJob));
}

export function listContentGroups() {
  return apiRequest<ContentGroup[]>("/api/jobs/content-groups").then((groups) =>
    Array.isArray(groups) ? groups.map(normalizeContentGroup) : []
  );
}

export function createContentGroup(payload: ContentGroupPayload) {
  return apiRequest<ContentGroup>("/api/jobs/content-groups", {
    method: "POST",
    body: JSON.stringify(payload)
  }).then(normalizeContentGroup);
}

export function createJob(payload: JobPayload) {
  return apiRequest<HermesJob>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload)
  }).then(normalizeJob);
}

export function getJob(jobId: string) {
  return apiRequest<HermesJob>(`/api/jobs/${encodeURIComponent(jobId)}`).then(normalizeJob);
}

export function updateJob(jobId: string, payload: JobPayload) {
  return apiRequest<HermesJob>(`/api/jobs/${encodeURIComponent(jobId)}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  }).then(normalizeJob);
}

export function deleteJob(jobId: string) {
  return apiRequest<null>(`/api/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
}

export function runJob(jobId: string) {
  return apiRequest<unknown>(`/api/jobs/${encodeURIComponent(jobId)}/run`, { method: "POST" });
}

export function pauseJob(jobId: string) {
  return apiRequest<unknown>(`/api/jobs/${encodeURIComponent(jobId)}/pause`, { method: "POST" });
}

export function resumeJob(jobId: string) {
  return apiRequest<unknown>(`/api/jobs/${encodeURIComponent(jobId)}/resume`, { method: "POST" });
}

export function listJobRuns(jobId: string) {
  return apiRequest<unknown>(`/api/jobs/${encodeURIComponent(jobId)}/runs`).then((data) => {
    if (Array.isArray(data)) return data.map(normalizeRun);
    if (data && typeof data === "object" && "runs" in data) {
      const runs = (data as { runs?: unknown }).runs;
      return Array.isArray(runs) ? runs.map(normalizeRun) : [];
    }
    return [];
  });
}

export function listAudit() {
  return apiRequest<unknown[]>("/api/audit").then((events) => events.map(normalizeAuditEvent));
}

export function listTemplates() {
  return apiRequest<ContentTemplate[]>("/api/templates").then((templates) =>
    Array.isArray(templates) ? templates.map(normalizeTemplate) : []
  );
}

export function createTemplate(payload: ContentTemplatePayload) {
  return apiRequest<ContentTemplate>("/api/templates", {
    method: "POST",
    body: JSON.stringify(payload)
  }).then(normalizeTemplate);
}

export function updateTemplate(templateId: number, payload: ContentTemplatePayload) {
  return apiRequest<ContentTemplate>(`/api/templates/${templateId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  }).then(normalizeTemplate);
}

export function deleteTemplate(templateId: number) {
  return apiRequest<{ id: number }>(`/api/templates/${templateId}`, { method: "DELETE" });
}

export function listCustomers() {
  return apiRequest<Customer[]>("/api/customers").then((customers) => (Array.isArray(customers) ? customers : []));
}

export function createCustomer(payload: CustomerPayload) {
  return apiRequest<Customer>("/api/customers", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateCustomer(customerId: number, payload: CustomerPayload) {
  return apiRequest<Customer>(`/api/customers/${customerId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteCustomer(customerId: number) {
  return apiRequest<{ id: number }>(`/api/customers/${customerId}`, { method: "DELETE" });
}

export function listSubscriptions(filters: SubscriptionFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== "all") {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return apiRequest<Subscription[]>(`/api/subscriptions${query ? `?${query}` : ""}`).then((subscriptions) =>
    Array.isArray(subscriptions) ? subscriptions : []
  );
}

export function createSubscription(payload: SubscriptionPayload) {
  return apiRequest<Subscription>("/api/subscriptions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateSubscription(subscriptionId: number, payload: SubscriptionPayload) {
  return apiRequest<Subscription>(`/api/subscriptions/${subscriptionId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteSubscription(subscriptionId: number) {
  return apiRequest<{ id: number }>(`/api/subscriptions/${subscriptionId}`, { method: "DELETE" });
}

export function getSubscriptionSummary() {
  return apiRequest<SubscriptionSummary>("/api/subscriptions/summary");
}

function normalizeHealth(data: unknown): HermesHealth {
  if (!data || typeof data !== "object") return {};
  const value = data as Record<string, unknown>;
  const cli = value.cli as Record<string, unknown> | undefined;
  const gateway = value.gateway as Record<string, unknown> | undefined;
  const cronData = value.cron_data as Record<string, unknown> | undefined;
  const outputDir = value.output_dir as Record<string, unknown> | undefined;
  const counts = value.job_counts as Record<string, unknown> | undefined;
  const last = value.last_admin_operation as Record<string, unknown> | null | undefined;

  return {
    cli_available: Boolean(value.cli_available ?? cli?.available),
    gateway_running: Boolean(value.gateway_running ?? gateway?.running),
    cron_readable: Boolean(value.cron_readable ?? cronData?.readable),
    output_readable: Boolean(value.output_readable ?? outputDir?.readable),
    last_operation_result:
      typeof value.last_operation_result === "string"
        ? value.last_operation_result
        : last
          ? `${String(last.operation ?? "operation")} ${String(last.status ?? "unknown")}`
          : null,
    total_jobs: numberFrom(value.total_jobs ?? counts?.total),
    active_jobs: numberFrom(value.active_jobs ?? counts?.active),
    paused_jobs: numberFrom(value.paused_jobs ?? counts?.paused),
    sync_problem_jobs: numberFrom(value.sync_problem_jobs ?? counts?.sync_problems),
    checks: {
      cli_available: Boolean(value.cli_available ?? cli?.available),
      gateway_running: Boolean(value.gateway_running ?? gateway?.running),
      cron_readable: Boolean(value.cron_readable ?? cronData?.readable),
      output_readable: Boolean(value.output_readable ?? outputDir?.readable)
    }
  };
}

function normalizeJob(job: HermesJob): HermesJob {
  const last = job.last_run_result;
  return {
    ...job,
    task_name: job.task_name || job.name,
    deliver: job.deliver || "local",
    skills: Array.isArray(job.skills) ? job.skills : [],
    last_run_result:
      last && typeof last === "object"
        ? `${String(last.operation ?? "operation")} ${String(last.status ?? "unknown")}`
        : last
  };
}

function normalizeContentGroup(group: ContentGroup): ContentGroup {
  return {
    ...group,
    skills: Array.isArray(group.skills) ? group.skills : [],
    deliveries: Array.isArray(group.deliveries)
      ? group.deliveries.map((delivery) => ({
          ...delivery,
          label: delivery.label || delivery.deliver,
          deliver: delivery.deliver || "local",
          last_run_result:
            delivery.last_run_result && typeof delivery.last_run_result === "object"
              ? `${String(delivery.last_run_result.operation ?? "operation")} ${String(
                  delivery.last_run_result.status ?? "unknown"
                )}`
              : delivery.last_run_result
        }))
      : []
  };
}

function normalizeTemplate(template: ContentTemplate): ContentTemplate {
  return {
    ...template,
    skills: Array.isArray(template.skills) ? template.skills : [],
    notes: template.notes ?? ""
  };
}

function normalizeRun(run: unknown): JobRun {
  const value = run && typeof run === "object" ? (run as Record<string, unknown>) : {};
  return {
    id: String(value.id ?? value.file_name ?? ""),
    file_name: typeof value.file_name === "string" ? value.file_name : undefined,
    path: typeof value.path === "string" ? value.path : undefined,
    size_bytes: typeof value.size_bytes === "number" ? value.size_bytes : undefined,
    modified_at: (value.modified_at as string | number | null | undefined) ?? null,
    started_at: (value.started_at as string | null | undefined) ?? null,
    finished_at: (value.finished_at as string | null | undefined) ?? null,
    status: String(value.status ?? "output"),
    output: typeof value.output === "string" ? value.output : typeof value.content === "string" ? value.content : null,
    error: typeof value.error === "string" ? value.error : null,
    content: typeof value.content === "string" ? value.content : null
  };
}

function normalizeAuditEvent(event: unknown): AuditEvent {
  const value = event && typeof event === "object" ? (event as Record<string, unknown>) : {};
  return {
    id: (value.id as string | number | undefined) ?? "",
    timestamp: String(value.timestamp ?? value.created_at ?? ""),
    operation_type: String(value.operation_type ?? value.operation ?? ""),
    target_job_id: String(value.target_job_id ?? value.hermes_job_id ?? ""),
    owner_label: String(value.owner_label ?? ""),
    request_summary: String(value.request_summary ?? ""),
    hermes_command_category: String(value.hermes_command_category ?? value.command_category ?? ""),
    result_status: String(value.result_status ?? value.status ?? "unknown"),
    error_message: String(value.error_message ?? "")
  };
}

function numberFrom(value: unknown): number {
  return typeof value === "number" ? value : 0;
}
