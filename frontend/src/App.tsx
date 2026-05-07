import { type FormEvent, useEffect, useMemo, useState } from "react";
import { ClipboardList, LayoutDashboard, LogOut, Plus, Tags, Users } from "lucide-react";
import {
  createCustomer,
  createSubscription,
  createTemplate,
  deleteCustomer,
  deleteSubscription,
  deleteTemplate,
  getSubscriptionSummary,
  getToken,
  listCustomers,
  listSubscriptions,
  listTemplates,
  login,
  logout,
  updateCustomer,
  updateSubscription,
  updateTemplate
} from "./api/client";
import type {
  ApiError,
  ContentTemplate,
  ContentTemplatePayload,
  Customer,
  CustomerPayload,
  Subscription,
  SubscriptionPayload,
  SubscriptionSummary
} from "./api/types";
import { FailureModal } from "./components/FailureModal";
import { ToastHost } from "./components/ToastHost";
import type { Language } from "./i18n";
import { LANGUAGE_KEY, readStoredLanguage, translations } from "./i18n";
import { parseSkillTags } from "./schedule";

type TabKey = "dashboard" | "customers" | "templates" | "subscriptions";

const channels = ["local", "feishu", "wechat", "qq"];
const subscriptionStatusFilters = [
  { value: "all", label: "全部状态" },
  { value: "active", label: "有效" },
  { value: "expiring_soon", label: "即将到期" },
  { value: "expired", label: "已到期" },
  { value: "paused", label: "暂停" }
];
const today = new Date().toISOString().slice(0, 10);
const emptyCustomer: CustomerPayload = { name: "", contact: "", status: "active", notes: "" };
const emptyTemplate: ContentTemplatePayload = { name: "", prompt: "", skills: [], notes: "" };
const emptySubscription: SubscriptionPayload = {
  customer_id: 0,
  content_template_id: null,
  deliver_channel: "feishu",
  deliver_address: "",
  frequency: "每天 08:00",
  start_date: today,
  duration_days: 30,
  status: "active",
  notes: ""
};

function toApiError(err: unknown, operation: string): ApiError {
  if (err && typeof err === "object" && "message" in err && "suggested_checks" in err) {
    return err as ApiError;
  }
  return {
    code: "NETWORK_ERROR",
    message: err instanceof Error ? err.message : "Unable to reach the Subscription Admin API.",
    operation,
    suggested_checks: ["Confirm the FastAPI backend is running.", "Confirm Nginx routes /api requests."]
  };
}

function channelLabel(channel: string) {
  return { local: "本地", feishu: "飞书", wechat: "微信", qq: "QQ" }[channel] ?? channel;
}

function expiryLabel(subscription: Subscription) {
  if (subscription.expiry_status === "permanent") return "永久";
  if (subscription.expiry_status === "expired") return "已到期";
  if (subscription.expiry_status === "expiring_soon") return `剩余 ${subscription.days_remaining ?? 0} 天`;
  if (typeof subscription.days_remaining === "number") return `剩余 ${subscription.days_remaining} 天`;
  return "未知";
}

function statusLabel(status: string, expiryStatus?: string) {
  if (expiryStatus === "expired" || status === "expired") return "已到期";
  if (expiryStatus === "expiring_soon") return "即将到期";
  return { active: "有效", paused: "暂停" }[status] ?? status;
}

function subscriptionMatchesSearch(subscription: Subscription, search: string) {
  const normalized = search.trim().toLowerCase();
  if (!normalized) return true;
  return [
    subscription.customer_name,
    subscription.content_template_name,
    subscription.deliver_channel,
    channelLabel(subscription.deliver_channel),
    subscription.deliver_address,
    subscription.frequency,
    subscription.notes
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

function subscriptionMatchesStatus(subscription: Subscription, filter: string) {
  if (filter === "all") return true;
  if (filter === "expired") return subscription.expiry_status === "expired" || subscription.status === "expired";
  if (filter === "expiring_soon") return subscription.expiry_status === "expiring_soon";
  return subscription.status === filter;
}

function LoginPage({ onSignedIn, onFailure }: { onSignedIn: () => void; onFailure: (error: ApiError) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    try {
      await login(username, password);
      onSignedIn();
    } catch (err) {
      onFailure(toApiError(err, "login"));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="loginShell">
      <form className="loginPanel" onSubmit={submit}>
        <div className="brandMark">
          <ClipboardList size={22} />
        </div>
        <p className="eyebrow">客户内容订阅管理台</p>
        <h1>Subscription Admin</h1>
        <label>
          <span>用户名</span>
          <input aria-label="用户名" value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label>
          <span>密码</span>
          <input
            aria-label="密码"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button type="submit" className="primaryButton fullButton" disabled={pending}>
          登录
        </button>
      </form>
    </main>
  );
}

function DashboardPage({ summary }: { summary: SubscriptionSummary | null }) {
  const recent = summary?.recent_subscriptions ?? [];
  return (
    <section className="pageStack">
      <header className="sectionHeader">
        <div>
          <p className="eyebrow">Subscription Admin</p>
          <h2>总览</h2>
        </div>
      </header>
      <div className="metricGrid">
        <div className="metric">
          <span>客户项目</span>
          <strong>{summary?.customer_count ?? 0}</strong>
        </div>
        <div className="metric">
          <span>有效订阅</span>
          <strong>{summary?.active_subscription_count ?? 0}</strong>
        </div>
        <div className="metric">
          <span>7 天内到期</span>
          <strong>{summary?.expiring_soon_count ?? 0}</strong>
        </div>
        <div className="metric dangerMetric">
          <span>已到期</span>
          <strong>{summary?.expired_subscription_count ?? 0}</strong>
        </div>
      </div>
      <section className="panel">
        <h3>最近订阅</h3>
        {recent.length === 0 ? (
          <p className="muted">暂无订阅。</p>
        ) : (
          <div className="runList">
            {recent.map((item) => (
              <article className="runItem" key={item.id}>
                <strong>
                  {item.customer_name} / {item.content_template_name || "未选择内容"}
                </strong>
                <span className="muted">
                  {channelLabel(item.deliver_channel)} / {expiryLabel(item)}
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

function CustomersPage({
  customers,
  onChanged,
  onFailure
}: {
  customers: Customer[];
  onChanged: () => void;
  onFailure: (error: ApiError) => void;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [payload, setPayload] = useState<CustomerPayload>(emptyCustomer);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (editingId) await updateCustomer(editingId, payload);
      else await createCustomer(payload);
      setEditingId(null);
      setPayload(emptyCustomer);
      onChanged();
    } catch (err) {
      onFailure(toApiError(err, "save_customer"));
    }
  }

  async function remove(id: number) {
    if (!window.confirm("删除这个客户项目？相关订阅也会删除。")) return;
    try {
      await deleteCustomer(id);
      onChanged();
    } catch (err) {
      onFailure(toApiError(err, "delete_customer"));
    }
  }

  return (
    <section className="pageStack">
      <header className="sectionHeader">
        <div>
          <p className="eyebrow">客户项目</p>
          <h2>客户项目</h2>
        </div>
      </header>
      <form className="formGrid panel" onSubmit={submit}>
        <label>
          <span>客户/项目名</span>
          <input
            aria-label="客户/项目名"
            value={payload.name}
            onChange={(event) => setPayload({ ...payload, name: event.target.value })}
            required
          />
        </label>
        <label>
          <span>联系方式</span>
          <input
            aria-label="联系方式"
            value={payload.contact ?? ""}
            onChange={(event) => setPayload({ ...payload, contact: event.target.value })}
          />
        </label>
        <label>
          <span>状态</span>
          <select
            aria-label="状态"
            value={payload.status ?? "active"}
            onChange={(event) => setPayload({ ...payload, status: event.target.value })}
          >
            <option value="active">有效</option>
            <option value="paused">暂停</option>
          </select>
        </label>
        <label className="wideField">
          <span>备注</span>
          <textarea
            value={payload.notes ?? ""}
            onChange={(event) => setPayload({ ...payload, notes: event.target.value })}
            rows={3}
          />
        </label>
        <div className="formActions wideField">
          <button className="primaryButton" type="submit">
            {editingId ? "保存客户" : "新增客户"}
          </button>
          {editingId ? (
            <button
              type="button"
              onClick={() => {
                setEditingId(null);
                setPayload(emptyCustomer);
              }}
            >
              取消
            </button>
          ) : null}
        </div>
      </form>
      <section className="contentGroups">
        {customers.map((customer) => (
          <article className="panel templateCard" key={customer.id}>
            <div>
              <h3>{customer.name}</h3>
              <p className="muted">
                {customer.contact || "无联系方式"} / {customer.status}
              </p>
            </div>
            <p className="preserve">{customer.notes}</p>
            <div className="buttonRow">
              <button
                onClick={() => {
                  setEditingId(customer.id);
                  setPayload({
                    name: customer.name,
                    contact: customer.contact,
                    status: customer.status,
                    notes: customer.notes ?? ""
                  });
                }}
              >
                编辑
              </button>
              <button className="dangerButton" onClick={() => remove(customer.id)}>
                删除
              </button>
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}

function TemplatesPage({
  templates,
  onChanged,
  onFailure
}: {
  templates: ContentTemplate[];
  onChanged: () => void;
  onFailure: (error: ApiError) => void;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [payload, setPayload] = useState<ContentTemplatePayload>(emptyTemplate);
  const [skillsText, setSkillsText] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nextPayload = { ...payload, skills: parseSkillTags(skillsText) };
    try {
      if (editingId) await updateTemplate(editingId, nextPayload);
      else await createTemplate(nextPayload);
      setEditingId(null);
      setPayload(emptyTemplate);
      setSkillsText("");
      onChanged();
    } catch (err) {
      onFailure(toApiError(err, "save_template"));
    }
  }

  async function remove(id: number) {
    if (!window.confirm("删除这个内容标签？")) return;
    try {
      await deleteTemplate(id);
      onChanged();
    } catch (err) {
      onFailure(toApiError(err, "delete_template"));
    }
  }

  return (
    <section className="pageStack">
      <header className="sectionHeader">
        <div>
          <p className="eyebrow">内容标签</p>
          <h2>内容标签</h2>
        </div>
      </header>
      <form className="formGrid panel" onSubmit={submit}>
        <label>
          <span>标签名</span>
          <input
            aria-label="标签名"
            value={payload.name}
            onChange={(event) => setPayload({ ...payload, name: event.target.value })}
            required
          />
        </label>
        <label>
          <span>Skills</span>
          <input aria-label="Skills" value={skillsText} onChange={(event) => setSkillsText(event.target.value)} />
        </label>
        <label className="wideField">
          <span>Prompt</span>
          <textarea
            aria-label="Prompt"
            value={payload.prompt}
            onChange={(event) => setPayload({ ...payload, prompt: event.target.value })}
            rows={7}
            required
          />
        </label>
        <label className="wideField">
          <span>备注</span>
          <textarea
            value={payload.notes ?? ""}
            onChange={(event) => setPayload({ ...payload, notes: event.target.value })}
            rows={3}
          />
        </label>
        <div className="formActions wideField">
          <button className="primaryButton" type="submit">
            {editingId ? "保存标签" : "新增标签"}
          </button>
          {editingId ? (
            <button
              type="button"
              onClick={() => {
                setEditingId(null);
                setPayload(emptyTemplate);
                setSkillsText("");
              }}
            >
              取消
            </button>
          ) : null}
        </div>
      </form>
      <section className="contentGroups">
        {templates.map((template) => (
          <article className="panel templateCard" key={template.id}>
            <div>
              <h3>{template.name}</h3>
              <p className="muted">{template.skills.join(", ") || "无 skills"}</p>
            </div>
            <p className="preserve">{template.prompt}</p>
            <div className="buttonRow">
              <button
                onClick={() => {
                  setEditingId(template.id);
                  setPayload({
                    name: template.name,
                    prompt: template.prompt,
                    skills: template.skills,
                    notes: template.notes ?? ""
                  });
                  setSkillsText(template.skills.join(", "));
                }}
              >
                编辑
              </button>
              <button className="dangerButton" onClick={() => remove(template.id)}>
                删除
              </button>
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}

function SubscriptionsPage({
  customers,
  templates,
  subscriptions,
  onChanged,
  onFailure
}: {
  customers: Customer[];
  templates: ContentTemplate[];
  subscriptions: Subscription[];
  onChanged: () => void;
  onFailure: (error: ApiError) => void;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [payload, setPayload] = useState<SubscriptionPayload>(emptySubscription);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filteredSubscriptions = useMemo(
    () =>
      subscriptions.filter(
        (subscription) => subscriptionMatchesSearch(subscription, search) && subscriptionMatchesStatus(subscription, statusFilter)
      ),
    [subscriptions, search, statusFilter]
  );

  useEffect(() => {
    if (!payload.customer_id && customers[0]) {
      setPayload((current) => ({ ...current, customer_id: customers[0].id }));
    }
  }, [customers, payload.customer_id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (editingId) await updateSubscription(editingId, payload);
      else await createSubscription(payload);
      setEditingId(null);
      setPayload({ ...emptySubscription, customer_id: customers[0]?.id ?? 0 });
      onChanged();
    } catch (err) {
      onFailure(toApiError(err, "save_subscription"));
    }
  }

  async function remove(id: number) {
    if (!window.confirm("删除这条订阅？")) return;
    try {
      await deleteSubscription(id);
      onChanged();
    } catch (err) {
      onFailure(toApiError(err, "delete_subscription"));
    }
  }

  return (
    <section className="pageStack">
      <header className="sectionHeader">
        <div>
          <p className="eyebrow">订阅</p>
          <h2>订阅</h2>
          <p className="muted">管理客户订阅周期、投递渠道和内容标签。</p>
        </div>
        <button
          className="primaryButton"
          onClick={() => {
            setEditingId(null);
            setPayload({ ...emptySubscription, customer_id: customers[0]?.id ?? 0, content_template_id: templates[0]?.id ?? null });
          }}
        >
          <Plus size={16} />
          新建订阅
        </button>
      </header>
      <section className="toolbar panel compactPanel">
        <label className="searchField">
          <span>搜索订阅</span>
          <input
            aria-label="搜索订阅"
            placeholder="客户、标签、渠道、地址或频率"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="compactField">
          <span>状态</span>
          <select
            aria-label="订阅状态筛选"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            {subscriptionStatusFilters.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <div className="stats">
          显示 {filteredSubscriptions.length} / {subscriptions.length}
        </div>
      </section>
      <form className="formGrid panel" onSubmit={submit}>
        <label>
          <span>客户项目</span>
          <select
            aria-label="客户项目"
            value={payload.customer_id}
            onChange={(event) => setPayload({ ...payload, customer_id: Number(event.target.value) })}
          >
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>内容标签</span>
          <select
            aria-label="内容标签"
            value={payload.content_template_id ?? ""}
            onChange={(event) =>
              setPayload({ ...payload, content_template_id: event.target.value ? Number(event.target.value) : null })
            }
          >
            <option value="">不选择</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>投递渠道</span>
          <select
            aria-label="投递渠道"
            value={payload.deliver_channel}
            onChange={(event) => setPayload({ ...payload, deliver_channel: event.target.value })}
          >
            {channels.map((channel) => (
              <option key={channel} value={channel}>
                {channelLabel(channel)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>投递地址</span>
          <input
            aria-label="投递地址"
            value={payload.deliver_address ?? ""}
            onChange={(event) => setPayload({ ...payload, deliver_address: event.target.value })}
          />
        </label>
        <label>
          <span>频率</span>
          <input
            aria-label="频率"
            value={payload.frequency ?? ""}
            onChange={(event) => setPayload({ ...payload, frequency: event.target.value })}
          />
        </label>
        <label>
          <span>开始日期</span>
          <input
            aria-label="开始日期"
            type="date"
            value={payload.start_date ?? ""}
            onChange={(event) => setPayload({ ...payload, start_date: event.target.value })}
          />
        </label>
        <label>
          <span>持续天数</span>
          <input
            aria-label="持续天数"
            type="number"
            min="1"
            value={payload.duration_days ?? ""}
            onChange={(event) => setPayload({ ...payload, duration_days: event.target.value ? Number(event.target.value) : null })}
          />
        </label>
        <label>
          <span>状态</span>
          <select
            aria-label="状态"
            value={payload.status ?? "active"}
            onChange={(event) => setPayload({ ...payload, status: event.target.value })}
          >
            <option value="active">有效</option>
            <option value="paused">暂停</option>
          </select>
        </label>
        <label className="wideField">
          <span>备注</span>
          <textarea
            value={payload.notes ?? ""}
            onChange={(event) => setPayload({ ...payload, notes: event.target.value })}
            rows={3}
          />
        </label>
        <div className="formActions wideField">
          <button className="primaryButton" type="submit" disabled={customers.length === 0}>
            {editingId ? "保存订阅" : "新增订阅"}
          </button>
        </div>
      </form>
      <section className="contentGroups">
        {filteredSubscriptions.length === 0 ? <div className="statePanel panel">没有符合条件的订阅。</div> : null}
        {filteredSubscriptions.map((item) => (
          <article
            className={`panel subscriptionCard subscription-${item.expiry_status}`}
            data-testid={`subscription-${item.id}`}
            key={item.id}
          >
            <div>
              <h3>{item.customer_name}</h3>
              <p className="muted">
                {item.content_template_name || "未选择内容标签"} / {channelLabel(item.deliver_channel)} / {item.frequency}
              </p>
              <p className="muted">{item.deliver_address}</p>
            </div>
            <div>
              <strong>{expiryLabel(item)}</strong>
              <p className="muted">{statusLabel(item.status, item.expiry_status)}</p>
            </div>
            <div className="buttonRow">
              <button
                onClick={() => {
                  setEditingId(item.id);
                  setPayload({
                    customer_id: item.customer_id,
                    content_template_id: item.content_template_id,
                    deliver_channel: item.deliver_channel,
                    deliver_address: item.deliver_address,
                    frequency: item.frequency,
                    start_date: item.start_date,
                    end_date: item.end_date,
                    duration_days: item.duration_days,
                    status: item.status,
                    notes: item.notes ?? ""
                  });
                }}
              >
                编辑
              </button>
              <button className="dangerButton" onClick={() => remove(item.id)}>
                删除
              </button>
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}

export default function App() {
  const [language, setLanguage] = useState<Language>(() => readStoredLanguage());
  const [authenticated, setAuthenticated] = useState(() => Boolean(getToken()));
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [summary, setSummary] = useState<SubscriptionSummary | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [templates, setTemplates] = useState<ContentTemplate[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [toast] = useState<string | null>(null);
  const t = translations[language];

  async function refreshAll() {
    try {
      const [nextSummary, nextCustomers, nextTemplates, nextSubscriptions] = await Promise.all([
        getSubscriptionSummary(),
        listCustomers(),
        listTemplates(),
        listSubscriptions()
      ]);
      setSummary(nextSummary);
      setCustomers(nextCustomers);
      setTemplates(nextTemplates);
      setSubscriptions(nextSubscriptions);
    } catch (err) {
      setError(toApiError(err, "refresh"));
    }
  }

  useEffect(() => {
    if (authenticated) void refreshAll();
  }, [authenticated]);

  if (!authenticated) {
    return (
      <>
        {error ? <FailureModal error={error} language={language} t={t} onClose={() => setError(null)} /> : null}
        <LoginPage onSignedIn={() => setAuthenticated(true)} onFailure={setError} />
      </>
    );
  }

  const navItems = [
    { key: "dashboard" as const, label: "总览", icon: LayoutDashboard },
    { key: "customers" as const, label: "客户项目", icon: Users },
    { key: "templates" as const, label: "内容标签", icon: Tags },
    { key: "subscriptions" as const, label: "订阅", icon: ClipboardList }
  ];
  const title = navItems.find((item) => item.key === activeTab)?.label ?? "总览";

  return (
    <main className="adminShell">
      <ToastHost message={toast} />
      {error ? <FailureModal error={error} language={language} t={t} onClose={() => setError(null)} /> : null}
      <aside className="sideNav">
        <div className="sideBrand">
          <ClipboardList size={20} />
          <div>
            <strong>Subscription Admin</strong>
            <span>客户内容订阅管理台</span>
          </div>
        </div>
        <nav aria-label="功能区">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={activeTab === item.key ? "navButton active" : "navButton"}
                onClick={() => setActiveTab(item.key)}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <button
          className="navButton logoutButton"
          onClick={async () => {
            await logout();
            setAuthenticated(false);
          }}
        >
          <LogOut size={16} />
          退出登录
        </button>
      </aside>
      <section className="contentShell">
        <header className="topBar">
          <div>
            <p className="eyebrow">Subscription Admin</p>
            <h1>{title}</h1>
          </div>
          <button
            onClick={() => {
              const next = language === "zh" ? "en" : "zh";
              localStorage.setItem(LANGUAGE_KEY, next);
              setLanguage(next);
            }}
          >
            {language === "zh" ? "中文 / EN" : "EN / 中文"}
          </button>
        </header>
        {activeTab === "dashboard" ? <DashboardPage summary={summary} /> : null}
        {activeTab === "customers" ? (
          <CustomersPage customers={customers} onChanged={() => void refreshAll()} onFailure={setError} />
        ) : null}
        {activeTab === "templates" ? (
          <TemplatesPage templates={templates} onChanged={() => void refreshAll()} onFailure={setError} />
        ) : null}
        {activeTab === "subscriptions" ? (
          <SubscriptionsPage
            customers={customers}
            templates={templates}
            subscriptions={subscriptions}
            onChanged={() => void refreshAll()}
            onFailure={setError}
          />
        ) : null}
      </section>
    </main>
  );
}
