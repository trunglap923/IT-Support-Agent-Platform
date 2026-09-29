import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CitationExcerpt } from "./CitationExcerpt";

describe("CitationExcerpt", () => {
  it("shows a short excerpt without expansion controls", () => {
    render(<CitationExcerpt excerpt={"## Setup\nShort supporting evidence."} />);

    expect(screen.getByText("Setup Short supporting evidence.")).toBeInTheDocument();
    expect(screen.queryByText(/##/)).not.toBeInTheDocument();
    expect(screen.queryByText("Xem đầy đủ")).not.toBeInTheDocument();
  });

  it("collapses a long excerpt and keeps the full evidence available", () => {
    const excerpt = "A".repeat(260);
    const { container } = render(
      <CitationExcerpt excerpt={excerpt} previewLength={40} />,
    );

    expect(container.querySelector("details")).not.toHaveAttribute("open");
    expect(screen.getByText("A".repeat(40) + "…")).toBeInTheDocument();
    expect(screen.getByText("Xem đầy đủ")).toBeInTheDocument();
    expect(screen.getByText(excerpt)).toBeInTheDocument();
  });
});
