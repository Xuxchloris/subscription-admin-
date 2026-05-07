import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { FailureModal } from "../src/components/FailureModal";
import { translations } from "../src/i18n";

test("renders operation failure details in Chinese", () => {
  render(
    <FailureModal
      t={translations.zh}
      error={{
        code: "OPERATION_FAILED",
        message: "Failed to save subscription.",
        operation: "create_subscription",
        hermes_output: "invalid schedule",
        suggested_checks: ["Check the schedule format."]
      }}
      onClose={() => undefined}
    />
  );

  expect(screen.getByText("操作失败")).toBeInTheDocument();
  expect(screen.getByText("Failed to save subscription.")).toBeInTheDocument();
  expect(screen.getByText("invalid schedule")).toBeInTheDocument();
  expect(screen.getByText("检查定时表达式格式。")).toBeInTheDocument();
});
