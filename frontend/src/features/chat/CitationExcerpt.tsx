const DEFAULT_PREVIEW_LENGTH = 220;

interface CitationExcerptProps {
  excerpt: string;
  previewLength?: number;
}

export function CitationExcerpt({
  excerpt,
  previewLength = DEFAULT_PREVIEW_LENGTH,
}: CitationExcerptProps) {
  const plainExcerpt = excerpt
    .replace(/(^|\s)#{1,6}\s+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();

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
