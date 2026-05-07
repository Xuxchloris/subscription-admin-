export type Language = "zh" | "en";

export const LANGUAGE_KEY = "hermes_admin_language";

const commonSuggestedChecks = {
  "Check the schedule format.": {
    zh: "检查定时表达式格式。",
    en: "Check the schedule format."
  },
  "Open the recent run output.": {
    zh: "打开最近一次运行输出。",
    en: "Open the recent run output."
  },
  "Check the prompt, delivery target, credentials, and selected skills.": {
    zh: "检查 prompt、投递目标、凭据和已选 skills。",
    en: "Check the prompt, delivery target, credentials, and selected skills."
  }
} as const;

const status = {
  active: "有效",
  paused: "暂停",
  unknown: "未知",
  synced: "已同步",
  pending_confirmation: "待确认",
  sync_error: "同步异常",
  last_operation_failed: "上次操作失败",
  success: "成功",
  succeeded: "已成功",
  failed: "失败",
  error: "错误",
  output: "输出"
};

export const translations = {
  en: {
    modal: {
      title: "Operation failed",
      close: "Close failure dialog",
      operation: "Operation",
      hermesOutput: "Command output",
      suggestedChecks: "Suggested checks"
    },
    status: {
      active: "active",
      paused: "paused",
      unknown: "unknown",
      synced: "synced",
      pending_confirmation: "pending confirmation",
      sync_error: "sync error",
      last_operation_failed: "last operation failed",
      success: "success",
      succeeded: "succeeded",
      failed: "failed",
      error: "error",
      output: "output"
    },
    jobs: {
      operations: "Operations",
      title: "Generated deliveries",
      expiry: "Expiry",
      permanent: "Permanent",
      expired: "Expired",
      expiresToday: "Expires today",
      remainingDays: (days: number) => `${days} days left`,
      lede: "Review generated delivery records when Hermes compatibility is enabled.",
      newTask: "New Content",
      refresh: "Refresh",
      filter: "Filter",
      filterPlaceholder: "Owner, content, delivery, schedule, skill",
      filterAria: "Filter content",
      status: "Status",
      delivery: "Delivery",
      sync: "Sync",
      all: "All",
      active: "Active",
      paused: "Paused",
      unknown: "Unknown",
      synced: "Synced",
      pending: "Pending",
      syncError: "Sync error",
      failed: "Failed",
      jobsCount: (count: number) => `${count} deliveries`,
      activeCount: (count: number) => `${count} active`,
      pausedCount: (count: number) => `${count} paused`,
      aria: "Generated deliveries",
      loading: "Loading content...",
      empty: "No content matches the current filter.",
      task: "Content",
      owner: "Owner",
      schedule: "Schedule",
      nextRun: "Next run",
      deliver: "Deliver",
      skills: "Skills",
      actions: "Actions",
      unassigned: "Unassigned",
      local: "local",
      none: "None",
      confirmDelete: "Delete this delivery?",
      runPolling: "Run requested. Checking result...",
      runSucceeded: "Run succeeded. Latest output was found.",
      actionLabels: {
        run: "Run requested.",
        pause: "Task paused.",
        resume: "Task resumed.",
        delete: "Task deleted."
      },
      titles: {
        view: "View details",
        edit: "Edit",
        run: "Run now",
        pause: "Pause",
        resume: "Resume",
        delete: "Delete"
      },
      ariaLabels: {
        view: (name: string) => `View ${name}`,
        edit: (name: string) => `Edit ${name}`,
        run: (name: string) => `Run ${name}`,
        pause: (name: string) => `Pause ${name}`,
        resume: (name: string) => `Resume ${name}`,
        delete: (name: string) => `Delete ${name}`
      }
    }
  },
  zh: {
    modal: {
      title: "操作失败",
      close: "关闭失败弹窗",
      operation: "操作",
      hermesOutput: "命令输出",
      suggestedChecks: "建议检查"
    },
    status,
    jobs: {
      operations: "操作",
      title: "生成的投递记录",
      expiry: "到期",
      permanent: "永久",
      expired: "已到期",
      expiresToday: "今天到期",
      remainingDays: (days: number) => `剩余 ${days} 天`,
      lede: "启用 Hermes 兼容能力时，可在这里查看生成的投递记录。",
      newTask: "新建内容",
      refresh: "刷新",
      filter: "筛选",
      filterPlaceholder: "归属、内容、投递、时间、skill",
      filterAria: "筛选内容",
      status: "状态",
      delivery: "投递",
      sync: "同步",
      all: "全部",
      active: "有效",
      paused: "暂停",
      unknown: "未知",
      synced: "已同步",
      pending: "待确认",
      syncError: "同步异常",
      failed: "失败",
      jobsCount: (count: number) => `${count} 个投递`,
      activeCount: (count: number) => `${count} 个有效`,
      pausedCount: (count: number) => `${count} 个暂停`,
      aria: "生成的投递记录",
      loading: "正在加载内容...",
      empty: "当前筛选条件下没有内容。",
      task: "内容",
      owner: "归属",
      schedule: "发布时间/频率",
      nextRun: "下次运行",
      deliver: "投递地址",
      skills: "Skills",
      actions: "操作",
      unassigned: "未分配",
      local: "local",
      none: "无",
      confirmDelete: "确定删除这个投递记录？",
      runPolling: "已请求立即运行，正在检查结果...",
      runSucceeded: "立即运行成功，已读取到最新结果。",
      actionLabels: {
        run: "已请求立即运行。",
        pause: "任务已暂停。",
        resume: "任务已恢复。",
        delete: "任务已删除。"
      },
      titles: {
        view: "查看详情",
        edit: "编辑",
        run: "立即运行",
        pause: "暂停",
        resume: "恢复",
        delete: "删除"
      },
      ariaLabels: {
        view: (name: string) => `查看 ${name}`,
        edit: (name: string) => `编辑 ${name}`,
        run: (name: string) => `运行 ${name}`,
        pause: (name: string) => `暂停 ${name}`,
        resume: (name: string) => `恢复 ${name}`,
        delete: (name: string) => `删除 ${name}`
      }
    }
  }
};

export type Translation = typeof translations.en;

export function readStoredLanguage(): Language {
  return localStorage.getItem(LANGUAGE_KEY) === "en" ? "en" : "zh";
}

export function translateSuggestedCheck(check: string, language: Language) {
  const translated = commonSuggestedChecks[check as keyof typeof commonSuggestedChecks];
  return translated?.[language] ?? check;
}
