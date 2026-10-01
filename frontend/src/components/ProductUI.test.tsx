// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Drawer, StatusBadge } from "./ProductUI";

describe("ProductUI", () => {
  it("maps machine statuses to readable labels", () => {
    render(<StatusBadge value="in_progress" />);
    expect(screen.getByText("Đang xử lý")).toHaveClass("warning");
  });

  it("closes a drawer with Escape and restores focus", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <><button type="button">Mở drawer</button><Drawer onClose={onClose} open={false} title="Tạo ticket"><input aria-label="Tiêu đề" /></Drawer></>,
    );
    const trigger = screen.getByRole("button", { name: "Mở drawer" });
    trigger.focus();
    rerender(
      <><button type="button">Mở drawer</button><Drawer onClose={onClose} open title="Tạo ticket"><input aria-label="Tiêu đề" /></Drawer></>,
    );
    expect(screen.getByRole("button", { name: "Đóng Tạo ticket" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    rerender(
      <><button type="button">Mở drawer</button><Drawer onClose={onClose} open={false} title="Tạo ticket"><input aria-label="Tiêu đề" /></Drawer></>,
    );
    expect(screen.getByRole("button", { name: "Mở drawer" })).toHaveFocus();
  });
});
