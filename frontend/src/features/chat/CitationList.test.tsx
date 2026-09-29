import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChatCitation } from "../../api/chat";
import { CitationList } from "./CitationList";

describe("CitationList", () => {
  it("groups sources from one document and removes duplicate title excerpts", () => {
    const citations: ChatCitation[] = [
      {
        source_id: "src-title",
        source_url: "/sources/src-title",
        document_id: "doc-vpn",
        title: "Thiết lập VPN demo",
        page_number: null,
        excerpt: "# Thiết lập VPN demo",
      },
      {
        source_id: "src-steps",
        source_url: "/sources/src-steps",
        document_id: "doc-vpn",
        title: "Thiết lập VPN demo",
        page_number: 2,
        excerpt: "## Ubuntu\nCài client và đăng nhập SSO.",
      },
      {
        source_id: "src-steps-copy",
        source_url: "/sources/src-steps-copy",
        document_id: "doc-vpn",
        title: "Thiết lập VPN demo",
        page_number: 2,
        excerpt: "## Ubuntu\nCài client và đăng nhập SSO.",
      },
    ];

    const { container } = render(<CitationList citations={citations} />);

    expect(screen.getAllByText("Thiết lập VPN demo")).toHaveLength(1);
    expect(screen.getAllByText("Ubuntu Cài client và đăng nhập SSO.")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Nguồn 1" })).toHaveAttribute(
      "data-source-id",
      "src-title",
    );
    expect(screen.getByRole("link", { name: "Nguồn 2 · Trang 2" })).toHaveAttribute(
      "data-source-id",
      "src-steps",
    );
    expect(container.querySelectorAll(".citation-list > li")).toHaveLength(1);
  });
});
