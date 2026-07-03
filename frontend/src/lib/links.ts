// Resolve a paper to an external URL. Prefer the stored `url`; otherwise derive
// one from the canonical id ("arxiv:2401.00001" -> arxiv abs page; "doi:10..." or
// a bare DOI -> doi.org; "openalex:W123" -> openalex.org). Returns null if nothing
// usable can be built, so callers can fall back to plain text.
export function paperHref(p: { url?: string | null; id?: string | null }): string | null {
  const url = (p.url || "").trim();
  if (url) return url;
  const id = (p.id || "").trim();
  if (!id) return null;
  const [scheme, ...rest] = id.split(":");
  const tail = rest.join(":");
  switch (scheme) {
    case "arxiv":
      return `https://arxiv.org/abs/${tail.replace(/^arxiv:/i, "")}`;
    case "doi":
      return `https://doi.org/${tail}`;
    case "openalex":
      return `https://openalex.org/${tail}`;
    default:
      return /^10\.\d{4,}\//.test(id) ? `https://doi.org/${id}` : null;
  }
}
