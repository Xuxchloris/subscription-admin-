import { useEffect, useMemo, useState } from "react";
import { Edit3, Eye, Pause, Play, Plus, RefreshCw, Trash2 } from "lucide-react";
import { deleteJob, listContentGroups, listJobRuns, pauseJob, resumeJob, runJob } from "../api/client";
import type { ApiError, ContentDelivery, ContentGroup, HermesJob, JobRun } from "../api/types";
import { FailureModal } from "../components/FailureModal";
import { StatusBadge } from "../components/StatusBadge";
import { ToastHost } from "../components/ToastHost";
import type { Language, Translation } from "../i18n";
import { translations } from "../i18n";

type ActionKey = "run" | "pause" | "resume" | "delete" | null;

type Props = {
  refreshKey?: number;
  language?: Language;
  t?: Translation;
  onNewTask: () => void;
  onEdit: (job: HermesJob) => void;
  onSelect: (job: HermesJob) => void;
  onOperation?: () => void;
};

function formatLastRun(result: HermesJob["last_run_result"]) {
  if (!result) return "";
  if (typeof result === "string") return result;
  return `${String(result.operation ?? "operation")} ${String(result.status ?? "unknown")}`;
}

function toApiError(err: unknown, operation = "load_jobs"): ApiError {
  if (err && typeof err === "object" && "message" in err && "suggested_checks" in err) {
    return err as ApiError;
  }

  return {
    code: "NETWORK_ERROR",
    message: err instanceof Error ? err.message : "Unable to reach the Hermes Admin API.",
    operation,
    suggested_checks: ["Confirm the FastAPI backend is running.", "Confirm the reverse proxy routes /api requests."]
  };
}

function deliveryName(delivery: ContentDelivery) {
  return delivery.label || delivery.deliver || delivery.job_id;
}

function deliveryToJob(group: ContentGroup, delivery: ContentDelivery): HermesJob {
  return {
    id: delivery.job_id,
    name: deliveryName(delivery),
    task_name: group.title,
    owner_label: group.owner_label,
    prompt: group.prompt,
    schedule: delivery.schedule,
    deliver: delivery.deliver,
    skills: group.skills,
    status: delivery.status,
    sync_status: delivery.sync_status,
    last_run_result: delivery.last_run_result,
    next_run_at: delivery.next_run_at,
    notes: group.notes,
    content_id: group.content_id,
    content_title: group.title,
    delivery_label: delivery.label
  };
}

function runLooksFailed(run: JobRun) {
  const status = String(run.status ?? "").toLowerCase();
  const text = `${run.error ?? ""}\n${run.output ?? ""}\n${run.content ?? ""}`.toLowerCase();
  return Boolean(run.error) || status.includes("fail") || status.includes("error") || text.includes("traceback") || text.includes("error:");
}

function expiryLabel(
  item: Pick<ContentGroup | ContentDelivery, "expiry_status" | "seconds_remaining">,
  t: Translation
) {
  if (!item.expiry_status || item.expiry_status === "permanent") return t.jobs.permanent;
  if (item.expiry_status === "expired") return t.jobs.expired;
  if (item.expiry_status === "expires_today") return t.jobs.expiresToday;
  if (typeof item.seconds_remaining === "number") {
    const days = Math.max(1, Math.ceil(item.seconds_remaining / 86_400));
    return t.jobs.remainingDays(days);
  }
  return t.jobs.unknown;
}

export function JobsPage({ refreshKey = 0, language = "zh", t = translations[language], onNewTask, onEdit, onSelect, onOperation }: Props) {
  const [groups, setGroups] = useState<ContentGroup[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [deliverFilter, setDeliverFilter] = useState("all");
  const [syncFilter, setSyncFilter] = useState("all");
  const [error, setError] = useState<ApiError | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setGroups(await listContentGroups());
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setLoading(false);
    }
  }

  async function pollRunResult(jobId: string) {
    const runs = await listJobRuns(jobId);
    const latest = runs[0];
    if (!latest) return false;
    if (runLooksFailed(latest)) {
      throw {
        code: "HERMES_RUN_FAILED",
        message: "Hermes reported a failed run.",
        operation: "run_job",
        hermes_output: latest.error || latest.output || latest.content || "",
        suggested_checks: ["Open the recent run output.", "Check the prompt, delivery target, credentials, and selected skills."]
      } satisfies ApiError;
    }
    return true;
  }

  async function action(jobId: string, actionName: Exclude<ActionKey, null>) {
    const confirmationNeeded = actionName === "delete";
    if (confirmationNeeded && !window.confirm(t.jobs.confirmDelete)) {
      return;
    }

    setBusyJobId(jobId);
    try {
      if (actionName === "delete") await deleteJob(jobId);
      if (actionName === "pause") await pauseJob(jobId);
      if (actionName === "resume") await resumeJob(jobId);
      if (actionName === "run") {
        setToast(t.jobs.runPolling);
        await runJob(jobId);
        const hasOutput = await pollRunResult(jobId);
        setToast(hasOutput ? t.jobs.runSucceeded : t.jobs.actionLabels.run);
      } else {
        setToast(t.jobs.actionLabels[actionName]);
      }
      await refresh();
      onOperation?.();
    } catch (err) {
      setError(toApiError(err, actionName === "run" ? "run_job" : `${actionName}_job`));
    } finally {
      setBusyJobId(null);
    }
  }

  useEffect(() => {
    void refresh();
  }, [refreshKey]);

  const filteredGroups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return groups
      .map((group) => ({
        ...group,
        deliveries: group.deliveries.filter((delivery) => {
          if (statusFilter !== "all" && delivery.status !== statusFilter) return false;
          if (deliverFilter !== "all" && delivery.deliver !== deliverFilter) return false;
          if (syncFilter !== "all" && (delivery.sync_status ?? "synced") !== syncFilter) return false;
          if (!needle) return true;
          const lastRun = formatLastRun(delivery.last_run_result);
          const haystack = [
            group.content_id,
            group.title,
            group.owner_label,
            group.prompt,
            group.skills.join(" "),
            delivery.job_id,
            delivery.label ?? "",
            delivery.schedule,
            delivery.deliver,
            delivery.sync_status ?? "",
            lastRun
          ]
            .join(" ")
            .toLowerCase();
          return haystack.includes(needle);
        })
      }))
      .filter((group) => group.deliveries.length > 0);
  }, [deliverFilter, groups, query, statusFilter, syncFilter]);

  const allDeliveries = useMemo(() => groups.flatMap((group) => group.deliveries), [groups]);
  const deliveryTargets = useMemo(
    () => Array.from(new Set(allDeliveries.map((delivery) => delivery.deliver).filter(Boolean))).sort(),
    [allDeliveries]
  );

  return (
    <section className="pageStack">
      <ToastHost message={toast} />
      {error ? <FailureModal error={error} language={language} t={t} onClose={() => setError(null)} /> : null}

      <header className="sectionHeader">
        <div className="titleBlock">
          <p className="eyebrow">{t.jobs.operations}</p>
          <h2>{t.jobs.title}</h2>
          <p className="lede">{t.jobs.lede}</p>
        </div>
        <div className="buttonRow">
          <button type="button" className="primaryButton" onClick={onNewTask}>
            <Plus size={16} />
            {t.jobs.newTask}
          </button>
          <button type="button" onClick={refresh} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            {t.jobs.refresh}
          </button>
        </div>
      </header>

      <section className="toolbar">
        <label className="searchField">
          <span>{t.jobs.filter}</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t.jobs.filterPlaceholder}
            aria-label={t.jobs.filterAria}
          />
        </label>
        <label className="compactField">
          <span>{t.jobs.status}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label={t.jobs.status}>
            <option value="all">{t.jobs.all}</option>
            <option value="active">{t.jobs.active}</option>
            <option value="paused">{t.jobs.paused}</option>
            <option value="unknown">{t.jobs.unknown}</option>
          </select>
        </label>
        <label className="compactField">
          <span>{t.jobs.delivery}</span>
          <select value={deliverFilter} onChange={(event) => setDeliverFilter(event.target.value)} aria-label={t.jobs.delivery}>
            <option value="all">{t.jobs.all}</option>
            {deliveryTargets.map((target) => (
              <option key={target} value={target}>
                {target}
              </option>
            ))}
          </select>
        </label>
        <label className="compactField">
          <span>{t.jobs.sync}</span>
          <select value={syncFilter} onChange={(event) => setSyncFilter(event.target.value)} aria-label={t.jobs.sync}>
            <option value="all">{t.jobs.all}</option>
            <option value="synced">{t.jobs.synced}</option>
            <option value="pending_confirmation">{t.jobs.pending}</option>
            <option value="sync_error">{t.jobs.syncError}</option>
            <option value="last_operation_failed">{t.jobs.failed}</option>
          </select>
        </label>
        <div className="stats">
          <span>{t.jobs.jobsCount(allDeliveries.length)}</span>
          <span>{t.jobs.activeCount(allDeliveries.filter((delivery) => delivery.status === "active").length)}</span>
          <span>{t.jobs.pausedCount(allDeliveries.filter((delivery) => delivery.status === "paused").length)}</span>
        </div>
      </section>

      <section aria-label={t.jobs.aria} className="contentGroups">
        {loading ? (
          <div className="statePanel panel">{t.jobs.loading}</div>
        ) : filteredGroups.length === 0 ? (
          <div className="statePanel panel">{t.jobs.empty}</div>
        ) : (
          filteredGroups.map((group) => (
            <article key={group.content_id} className="contentGroup panel">
              <header className="contentGroupHeader">
                <div>
                  <h3>{group.title}</h3>
                  <div className="muted">{group.owner_label || t.jobs.unassigned}</div>
                  <div className="muted">{group.content_template_name || "-"}</div>
                  <div className="muted">{`${t.jobs.expiry}: ${expiryLabel(group, t)}`}</div>
                  <div className="muted">{group.skills.length > 0 ? group.skills.join(", ") : t.jobs.none}</div>
                </div>
                <span className="mono">{group.content_id}</span>
              </header>

              <div className="deliveryTable">
                {group.deliveries.map((delivery) => {
                  const job = deliveryToJob(group, delivery);
                  const name = deliveryName(delivery);
                  return (
                    <div key={delivery.job_id} className="deliveryRow">
                      <div>
                        <div className="jobTitle">{name}</div>
                        <div className="muted mono">{delivery.job_id}</div>
                        {delivery.last_run_result ? <div className="muted">{formatLastRun(delivery.last_run_result)}</div> : null}
                      </div>
                      <StatusBadge status={delivery.status ?? "unknown"} t={t} />
                      <StatusBadge status={delivery.sync_status ?? "synced"} tone="sync" t={t} />
                      <div>
                        <div>{delivery.schedule || t.jobs.unknown}</div>
                        <div className="muted">{delivery.next_run_at || t.jobs.unknown}</div>
                        <div className="muted">{expiryLabel(delivery, t)}</div>
                      </div>
                      <div>{delivery.deliver || t.jobs.local}</div>
                      <div className="actions">
                        <button
                          type="button"
                          onClick={() => onSelect(job)}
                          disabled={busyJobId === delivery.job_id}
                          aria-label={t.jobs.ariaLabels.view(name)}
                          title={t.jobs.titles.view}
                        >
                          <Eye size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => onEdit(job)}
                          disabled={busyJobId === delivery.job_id}
                          aria-label={t.jobs.ariaLabels.edit(name)}
                          title={t.jobs.titles.edit}
                        >
                          <Edit3 size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => action(delivery.job_id, "run")}
                          disabled={busyJobId === delivery.job_id}
                          aria-label={t.jobs.ariaLabels.run(name)}
                          title={t.jobs.titles.run}
                        >
                          <Play size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => action(delivery.job_id, "pause")}
                          disabled={busyJobId === delivery.job_id}
                          aria-label={t.jobs.ariaLabels.pause(name)}
                          title={t.jobs.titles.pause}
                        >
                          <Pause size={16} />
                        </button>
                        <button
                          type="button"
                          onClick={() => action(delivery.job_id, "resume")}
                          disabled={busyJobId === delivery.job_id}
                          aria-label={t.jobs.ariaLabels.resume(name)}
                          title={t.jobs.titles.resume}
                        >
                          <RefreshCw size={16} />
                        </button>
                        <button
                          type="button"
                          className="dangerButton"
                          onClick={() => action(delivery.job_id, "delete")}
                          disabled={busyJobId === delivery.job_id}
                          aria-label={t.jobs.ariaLabels.delete(name)}
                          title={t.jobs.titles.delete}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </article>
          ))
        )}
      </section>
    </section>
  );
}
