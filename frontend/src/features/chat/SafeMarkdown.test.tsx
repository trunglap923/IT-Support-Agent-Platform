import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SafeMarkdown } from "./SafeMarkdown";

describe("SafeMarkdown", () => {
  it("renders line breaks, lists, emphasis, and code", () => {
    const { container } = render(
      <SafeMarkdown
        content={"First line\nSecond line\n\n- Check VPN\n- Restart client\n\nUse **carefully** and run `status`."}
      />,
    );

    expect(container.querySelector("br")).toBeInTheDocument();
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByText("carefully").tagName).toBe("STRONG");
    expect(screen.getByText("status").tagName).toBe("CODE");
  });

  it("renders compact headings and does not render raw HTML", () => {
    const { container } = render(
      <SafeMarkdown content={"# Troubleshooting\n\n<script>alert('unsafe')</script>\n\nSafe text"} />,
    );

    expect(screen.getByRole("heading", { name: "Troubleshooting" })).toBeInTheDocument();
    expect(container.querySelector("script")).not.toBeInTheDocument();
    expect(screen.getByText("Safe text")).toBeInTheDocument();
  });

  it("restores a heading joined to the previous evidence excerpt", () => {
    const { container } = render(
      <SafeMarkdown content={"Keep the token private. ## Escalation data\nInclude the request ID."} />,
    );

    expect(screen.getByRole("heading", { name: "Escalation data" })).toBeInTheDocument();
    expect(container).not.toHaveTextContent("## Escalation data");
  });

  it("unwraps links instead of creating navigable content", () => {
    const { container } = render(
      <SafeMarkdown content={"Open [this link](javascript:alert('unsafe'))."} />,
    );

    expect(container.querySelector("a")).not.toBeInTheDocument();
    expect(container.querySelector("p")).toHaveTextContent("Open this link.");
  });
});
