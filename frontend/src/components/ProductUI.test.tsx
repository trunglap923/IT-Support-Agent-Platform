// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button, Drawer, SearchField, StatusBadge, Tabs, TextField, Toolbar } from "./ProductUI";

describe("ProductUI", () => {
  it("maps machine statuses to readable labels", () => {
    render(<StatusBadge value="in_progress" />);
    expect(screen.getByText("Đang xử lý")).toHaveClass("warning");
  });

  it("renders consistent button variants without submitting by default", () => {
    render(<Button variant="primary">Lưu thay đổi</Button>);
    const button = screen.getByRole("button", { name: "Lưu thay đổi" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveClass("product-button", "primary", "size-md");
  });

  it("associates field errors with their controls", () => {
    render(<TextField error="Giá trị không hợp lệ" label="Tên thiết bị" />);
    const input = screen.getByRole("textbox", { name: "Tên thiết bị" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Giá trị không hợp lệ");
  });

  it("provides accessible search, toolbar, and tab primitives", () => {
    const onChange = vi.fn();
    render(
      <Toolbar label="Bộ lọc ticket">
        <SearchField label="Tìm ticket" />
        <Tabs
          items={[{ value: "all", label: "Tất cả" }, { value: "open", label: "Đang mở" }]}
          label="Trạng thái ticket"
          onChange={onChange}
          value="all"
        />
      </Toolbar>,
    );
    expect(screen.getByRole("toolbar", { name: "Bộ lọc ticket" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Tìm ticket" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Tất cả" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Đang mở" }));
    expect(onChange).toHaveBeenCalledWith("open");
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
