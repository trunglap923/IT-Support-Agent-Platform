import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppErrorBoundary } from "./AppErrorBoundary";

function BrokenView(): never {
  throw new Error("secret raw detail");
}

describe("AppErrorBoundary", () => {
  it("renders a safe recovery screen without exposing the exception", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <AppErrorBoundary>
        <BrokenView />
      </AppErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Không thể hiển thị màn hình này");
    expect(screen.queryByText("secret raw detail")).not.toBeInTheDocument();
  });
});
