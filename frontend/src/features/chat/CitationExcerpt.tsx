import { normalizeCitationExcerpt } from "./citationText";

const DEFAULT_PREVIEW_LENGTH = 220;

interface CitationExcerptProps {
  excerpt: string;
  previewLength?: number;
}

export function CitationExcerpt({
  excerpt,
  previewLength = DEFAULT_PREVIEW_LENGTH,
}: CitationExcerptProps) {
  const plainExcerpt = normalizeCitationExcerpt(excerpt);

  if (plainExcerpt.length <= previewLength) {
    return <small className="citation-excerpt">{plainExcerpt}</small>;
  }

  const preview = plainExcerpt.slice(0, previewLength).trimEnd();

  return (
    <details className="citation-excerpt citation-excerpt-expandable">
      <summary>
        <span>{preview}…</span>
        <span className="citation-expand-label">Xem đầy đủ</span>
      </summary>
      <small>{plainExcerpt}</small>
    </details>
  );
}
