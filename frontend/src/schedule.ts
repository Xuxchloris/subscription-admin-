export type ScheduleMode = "every_30_minutes" | "daily" | "weekly" | "custom";

export type ScheduleDraft = {
  mode: ScheduleMode;
  time?: string;
  weekdays?: string[];
  cron?: string;
};

function parseTime(time: string | undefined) {
  if (!time || !/^\d{2}:\d{2}$/.test(time)) {
    throw new Error("time is required");
  }
  const [hourText, minuteText] = time.split(":");
  const hour = Number(hourText);
  const minute = Number(minuteText);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    throw new Error("time is invalid");
  }
  return { hour, minute };
}

export function buildCronSchedule(draft: ScheduleDraft) {
  if (draft.mode === "every_30_minutes") {
    return "*/30 * * * *";
  }

  if (draft.mode === "daily") {
    const { hour, minute } = parseTime(draft.time);
    return `${minute} ${hour} * * *`;
  }

  if (draft.mode === "weekly") {
    const { hour, minute } = parseTime(draft.time);
    const weekdays = [...new Set(draft.weekdays ?? [])].filter(Boolean).sort((a, b) => Number(a) - Number(b));
    if (weekdays.length === 0) {
      throw new Error("weekday is required");
    }
    return `${minute} ${hour} * * ${weekdays.join(",")}`;
  }

  const cron = draft.cron?.trim();
  if (!cron) {
    throw new Error("cron is required");
  }
  return cron;
}

export function parseSkillTags(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[,\s]+/)
        .map((skill) => skill.trim())
        .filter(Boolean)
    )
  );
}
