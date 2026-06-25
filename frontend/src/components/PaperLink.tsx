import { paperHref } from "../lib/links";

// A paper title/citation that links out to the source (arXiv/DOI/OpenAlex) when a
// URL can be resolved, else renders as plain text. Stops click propagation so it
// can sit inside clickable rows without triggering them.
export default function PaperLink({
  paper, children, className,
}: {
  paper: { url?: string | null; id?: string | null };
  children: React.ReactNode;
  className?: string;
}) {
  const href = paperHref(paper);
  if (!href) return <span className={className}>{children}</span>;
  return (
    <a
      className={`paper-link${className ? ` ${className}` : ""}`}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title="Open source ↗"
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </a>
  );
}
