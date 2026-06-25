import React from "react";

// Minimal, dependency-free, safe Markdown renderer for chat answers.
// Supports: headings, bold, italic, inline code, fenced code, bullet/numbered
// lists, links [text](url), and bare URLs. Builds React elements (no innerHTML).

const URL_SPLIT = /(https?:\/\/[^\s)]+)/g;

function linkify(text: string, kb: string): React.ReactNode[] {
  return text.split(URL_SPLIT).map((p, i) => {
    if (!p) return null;
    if (p.startsWith("http")) {
      return (
        <a key={`${kb}u${i}`} href={p} target="_blank" rel="noopener noreferrer" className="md-link">{p}</a>
      );
    }
    return <React.Fragment key={`${kb}f${i}`}>{p}</React.Fragment>;
  });
}

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]+\]\([^)]+\))/g;

function inline(text: string, kb: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0, i = 0, m: RegExpExecArray | null;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) out.push(...linkify(text.slice(last, m.index), `${kb}-${i++}`));
    const tok = m[0];
    if (tok.startsWith("`")) {
      out.push(<code key={`${kb}c${i++}`} className="md-code">{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("**")) {
      out.push(<strong key={`${kb}b${i++}`}>{inline(tok.slice(2, -2), `${kb}b${i}`)}</strong>);
    } else if (tok.startsWith("*")) {
      out.push(<em key={`${kb}i${i++}`}>{tok.slice(1, -1)}</em>);
    } else {
      const mm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      if (mm) out.push(<a key={`${kb}l${i++}`} href={mm[2]} target="_blank" rel="noopener noreferrer" className="md-link">{mm[1]}</a>);
      else out.push(tok);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(...linkify(text.slice(last), `${kb}-${i++}`));
  return out;
}

export default function Markdown({ text }: { text: string }) {
  const lines = (text || "").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  const isBlockStart = (l: string) => /^(#{1,3}\s|```|\s*[-*]\s|\s*\d+\.\s)/.test(l);
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      blocks.push(<pre className="md-pre" key={blocks.length}><code>{buf.join("\n")}</code></pre>);
      continue;
    }
    const h = /^(#{1,3})\s+(.*)/.exec(line);
    if (h) {
      const Tag = `h${Math.min(6, h[1].length + 3)}` as keyof React.JSX.IntrinsicElements;
      blocks.push(React.createElement(Tag, { key: blocks.length, className: "md-h" }, inline(h[2], `h${blocks.length}`)));
      i++; continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, "")); i++; }
      blocks.push(<ul className="md-ul" key={blocks.length}>{items.map((it, j) => <li key={j}>{inline(it, `ul${blocks.length}-${j}`)}</li>)}</ul>);
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*\d+\.\s+/, "")); i++; }
      blocks.push(<ol className="md-ol" key={blocks.length}>{items.map((it, j) => <li key={j}>{inline(it, `ol${blocks.length}-${j}`)}</li>)}</ol>);
      continue;
    }
    if (line.trim() === "") { i++; continue; }
    const buf = [line]; i++;
    while (i < lines.length && lines[i].trim() !== "" && !isBlockStart(lines[i])) { buf.push(lines[i]); i++; }
    blocks.push(<p className="md-p" key={blocks.length}>{inline(buf.join(" "), `p${blocks.length}`)}</p>);
  }
  return <div className="md">{blocks}</div>;
}
