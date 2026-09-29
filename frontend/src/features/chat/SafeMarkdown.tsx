import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";

const ALLOWED_ELEMENTS = [
  "p",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "code",
  "pre",
  "br",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
];

interface SafeMarkdownProps {
  content: string;
}

export function SafeMarkdown({ content }: SafeMarkdownProps) {
  const normalizedContent = content.replace(
    /([.!?])\s+(#{1,6}\s+)/g,
    "$1\n\n$2",
  );

  return (
    <div className="message-content">
      <Markdown
        allowedElements={ALLOWED_ELEMENTS}
        remarkPlugins={[remarkBreaks]}
        skipHtml
        unwrapDisallowed
      >
        {normalizedContent}
      </Markdown>
    </div>
  );
}
