import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom";
import { vi } from "vitest";
import App from "../src/App";

const jsonResponse = (data: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" }
    })
  );

const seedCustomers = [
  { id: 1, name: "客户A", contact: "alice@example.com", status: "active", notes: "" },
  { id: 2, name: "客户B", contact: "bob@example.com", status: "active", notes: "" }
];

const seedTemplates = [
  { id: 1, name: "AI 资讯", prompt: "抓取 AI 资讯", skills: ["trend-scout"], notes: "" },
  { id: 2, name: "小红书选题", prompt: "抓取小红书选题", skills: ["xhs"], notes: "" }
];

const seedSubscriptions = [
  {
    id: 1,
    customer_id: 1,
    customer_name: "客户A",
    content_template_id: 1,
    content_template_name: "AI 资讯",
    deliver_channel: "feishu",
    deliver_address: "飞书群",
    frequency: "每天 08:00",
    start_date: "2026-05-07",
    end_date: "2026-05-13",
    duration_days: 6,
    status: "active",
    expiry_status: "expiring_soon",
    days_remaining: 6,
    notes: ""
  },
  {
    id: 2,
    customer_id: 2,
    customer_name: "客户B",
    content_template_id: 2,
    content_template_name: "小红书选题",
    deliver_channel: "wechat",
    deliver_address: "微信群",
    frequency: "每周一 09:00",
    start_date: "2026-04-01",
    end_date: "2026-05-01",
    duration_days: 30,
    status: "expired",
    expiry_status: "expired",
    days_remaining: 0,
    notes: ""
  }
];

function mockApi({
  customers = [],
  templates = [],
  subscriptions = []
}: {
  customers?: unknown[];
  templates?: unknown[];
  subscriptions?: unknown[];
}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const path = input.toString();
    if (path === "/api/auth/login") {
      return jsonResponse({ success: true, data: { token: "admin-token", username: "admin" }, error: null });
    }
    if (path === "/api/auth/logout") {
      return jsonResponse({ success: true, data: null, error: null });
    }
    if (path === "/api/subscriptions/summary") {
      return jsonResponse({
        success: true,
        data: {
          customer_count: customers.length,
          active_subscription_count: subscriptions.filter((item) => (item as { status?: string }).status === "active").length,
          expiring_soon_count: subscriptions.filter((item) => (item as { expiry_status?: string }).expiry_status === "expiring_soon").length,
          expired_subscription_count: subscriptions.filter((item) => (item as { expiry_status?: string }).expiry_status === "expired").length,
          recent_subscriptions: subscriptions
        },
        error: null
      });
    }
    if (path === "/api/customers" && !init?.method) {
      return jsonResponse({ success: true, data: customers, error: null });
    }
    if (path === "/api/templates" && !init?.method) {
      return jsonResponse({ success: true, data: templates, error: null });
    }
    if (path === "/api/subscriptions" && !init?.method) {
      return jsonResponse({ success: true, data: subscriptions, error: null });
    }
    if (path === "/api/customers" && init?.method === "POST") {
      const customer = { id: customers.length + 1, name: "客户A", contact: "alice@example.com", status: "active", notes: "" };
      customers.push(customer);
      return jsonResponse({ success: true, data: customer, error: null });
    }
    if (path === "/api/templates" && init?.method === "POST") {
      const template = { id: templates.length + 1, name: "AI 资讯", prompt: "抓取 AI 资讯", skills: ["trend-scout"], notes: "" };
      templates.push(template);
      return jsonResponse({ success: true, data: template, error: null });
    }
    if (path === "/api/subscriptions" && init?.method === "POST") {
      const subscription = {
        id: subscriptions.length + 1,
        customer_id: 1,
        customer_name: "客户A",
        content_template_id: 1,
        content_template_name: "AI 资讯",
        deliver_channel: "feishu",
        deliver_address: "飞书群",
        frequency: "每天 08:00",
        status: "active",
        expiry_status: "active",
        days_remaining: 30
      };
      subscriptions.push(subscription);
      return jsonResponse({ success: true, data: subscription, error: null });
    }
    return jsonResponse({ success: true, data: null, error: null });
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

test("logs in and renders the subscription admin dashboard", async () => {
  const fetchMock = mockApi({
    customers: seedCustomers.slice(0, 1),
    templates: [],
    subscriptions: seedSubscriptions.slice(0, 1)
  });

  render(<App />);

  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "admin" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));

  expect(await screen.findByRole("button", { name: "总览" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "客户项目" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "内容标签" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "订阅" })).toBeInTheDocument();
  expect(screen.queryByText("Hermes Admin")).not.toBeInTheDocument();
  expect(screen.queryByText("内部运维")).not.toBeInTheDocument();
  expect(localStorage.getItem("hermes_admin_token")).toBe("admin-token");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/subscriptions/summary", expect.any(Object)));
});

test("creates a customer, a label, and a subscription", async () => {
  localStorage.setItem("hermes_admin_token", "admin-token");
  mockApi({ customers: [], templates: [], subscriptions: [] });

  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "客户项目" }));
  fireEvent.change(screen.getByLabelText("客户/项目名"), { target: { value: "客户A" } });
  fireEvent.change(screen.getByLabelText("联系方式"), { target: { value: "alice@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "新增客户" }));
  await screen.findByText("客户A");

  fireEvent.click(await screen.findByRole("button", { name: "内容标签" }));
  fireEvent.change(screen.getByLabelText("标签名"), { target: { value: "AI 资讯" } });
  fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "抓取 AI 资讯" } });
  fireEvent.change(screen.getByLabelText("Skills"), { target: { value: "trend-scout" } });
  fireEvent.click(screen.getByRole("button", { name: "新增标签" }));
  await screen.findByText("AI 资讯");

  fireEvent.click(await screen.findByRole("button", { name: "订阅" }));
  fireEvent.change(screen.getByLabelText("投递地址"), { target: { value: "飞书群" } });
  fireEvent.change(screen.getByLabelText("频率"), { target: { value: "每天 08:00" } });
  fireEvent.click(screen.getByRole("button", { name: "新增订阅" }));

  await screen.findByText("客户A");
  expect(screen.getByText("AI 资讯")).toBeInTheDocument();
});

test("filters subscriptions by search text and status while showing countdowns", async () => {
  localStorage.setItem("hermes_admin_token", "admin-token");
  mockApi({
    customers: [...seedCustomers],
    templates: [...seedTemplates],
    subscriptions: [...seedSubscriptions]
  });

  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "订阅" }));
  const activeCard = await screen.findByTestId("subscription-1");
  expect(within(activeCard).getByText("客户A")).toBeInTheDocument();
  expect(within(activeCard).getByText("剩余 6 天")).toBeInTheDocument();
  expect(screen.getByTestId("subscription-2")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("搜索订阅"), { target: { value: "飞书" } });
  expect(screen.getByTestId("subscription-1")).toBeInTheDocument();
  expect(screen.queryByTestId("subscription-2")).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("搜索订阅"), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText("订阅状态筛选"), { target: { value: "expired" } });
  expect(screen.queryByTestId("subscription-1")).not.toBeInTheDocument();
  const expiredCard = screen.getByTestId("subscription-2");
  expect(expiredCard).toBeInTheDocument();
  expect(within(expiredCard).getAllByText("已到期")).toHaveLength(2);
});
