import { describe, expect, test } from "vitest";
import { buildCronSchedule, parseSkillTags } from "../src/schedule";

describe("buildCronSchedule", () => {
  test("builds the supported schedule presets", () => {
    expect(buildCronSchedule({ mode: "every_30_minutes" })).toBe("*/30 * * * *");
    expect(buildCronSchedule({ mode: "daily", time: "08:30" })).toBe("30 8 * * *");
    expect(buildCronSchedule({ mode: "weekly", time: "06:30", weekdays: ["1", "4"] })).toBe("30 6 * * 1,4");
    expect(buildCronSchedule({ mode: "custom", cron: "15 10 * * 2" })).toBe("15 10 * * 2");
  });

  test("rejects incomplete preset inputs", () => {
    expect(() => buildCronSchedule({ mode: "daily", time: "" })).toThrow("time");
    expect(() => buildCronSchedule({ mode: "weekly", time: "06:30", weekdays: [] })).toThrow("weekday");
    expect(() => buildCronSchedule({ mode: "custom", cron: "" })).toThrow("cron");
  });
});

describe("parseSkillTags", () => {
  test("splits comma newline and whitespace separated skill tags", () => {
    expect(parseSkillTags("writer, web-search\nfeishu  writer")).toEqual(["writer", "web-search", "feishu"]);
  });
});
