import { BookOpenText, ExternalLink } from "lucide-react";

import type { ChatCitation } from "../../api/chat";
import { CitationExcerpt } from "./CitationExcerpt";
import { normalizeCitationExcerpt } from "./citationText";

interface CitationGroup {
  key: string;
  title: string;
  sources: ChatCitation[];
  excerpts: string[];
}

function normalizedKey(value: string) {
  return value.replace(/\s+/g, " ").trim().toLocaleLowerCase();
}

function groupCitations(citations: ChatCitation[]): CitationGroup[] {
  const groups = new Map<string, CitationGroup>();

  for (const citation of citations) {
    const title = citation.title.replace(/\s+/g, " ").trim();
    const key = citation.document_id ?? `title:${normalizedKey(title)}`;
    const group = groups.get(key) ?? { key, title, sources: [], excerpts: [] };
    const excerpt = normalizeCitationExcerpt(citation.excerpt);
    const excerptKey = normalizedKey(excerpt);

    group.sources.push(citation);
    if (
      excerpt &&
      excerptKey !== normalizedKey(title) &&
      !group.excerpts.some((value) => normalizedKey(value) === excerptKey)
    ) {
      group.excerpts.push(excerpt);
    }
    groups.set(key, group);
  }

  return [...groups.values()];
}

export function CitationList({ citations }: { citations: ChatCitation[] }) {
  const groups = groupCitations(citations);

  return (
    <section aria-label="Nguồn tham chiếu" className="citation-panel">
      <header className="citation-panel-heading">
        <span><BookOpenText aria-hidden="true" size={15} /> Nguồn tham chiếu</span>
        <small>{groups.length} tài liệu</small>
      </header>
      <ul className="citation-list">
      {groups.map((group, groupIndex) => (
        <li key={group.key}>
          <span className="citation-index" aria-hidden="true">{groupIndex + 1}</span>
          <div className="citation-copy">
            <strong>{group.title}</strong>
            <div className="citation-sources">
              {group.sources.map((source, index) => {
                const label =
                  group.sources.length === 1 ? "Mở nguồn" : `Nguồn ${index + 1}`;
                const page = source.page_number ? ` · Trang ${source.page_number}` : "";
                return source.source_url ? (
                  <a
                    data-source-id={source.source_id}
                    href={source.source_url}
                    key={source.source_id}
                    rel="noopener"
                    target="_blank"
                  >
                    {label}{page}<ExternalLink aria-hidden="true" size={12} />
                  </a>
                ) : (
                  <span data-source-id={source.source_id} key={source.source_id}>
                    {label}{page}
                  </span>
                );
              })}
            </div>
            {group.excerpts.map((excerpt) => (
              <CitationExcerpt excerpt={excerpt} key={excerpt} />
            ))}
          </div>
        </li>
      ))}
      </ul>
    </section>
  );
}
