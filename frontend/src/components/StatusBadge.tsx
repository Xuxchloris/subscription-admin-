import type { Translation } from "../i18n";

type Props = {
  status: string;
  tone?: "job" | "sync";
  t?: Translation;
};

export function StatusBadge({ status, tone = "job", t }: Props) {
  const safeStatus = status || "unknown";
  const label = t?.status[safeStatus as keyof Translation["status"]] ?? safeStatus.replace(/_/g, " ");
  return <span className={`badge badge-${tone} badge-${safeStatus}`}>{label}</span>;
}
