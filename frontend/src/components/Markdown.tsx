import { Children, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';

// The models write formulas as \( … \) and \[ … \]; remark-math expects $.
function normalizeMath(text: string) {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, body) => `\n$$${body}$$\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, body) => `$${body.trim()}$`);
}

const CITATION = /\[(\d{1,2})\]/g;

/** Turns "[2]" in plain text into clickable citation buttons. */
function withCitations(node: ReactNode, onCite: (n: number) => void): ReactNode {
  return Children.map(node, (child) => {
    if (typeof child === 'string') {
      const parts: ReactNode[] = [];
      let last = 0;

      for (const match of child.matchAll(CITATION)) {
        const n = Number(match[1]);
        parts.push(child.slice(last, match.index));
        parts.push(
          <button key={`${match.index}`} className="cite" onClick={() => onCite(n)} type="button">
            {n}
          </button>,
        );
        last = match.index + match[0].length;
      }

      parts.push(child.slice(last));
      return parts;
    }

    return child;
  });
}

export function Markdown({
  children,
  onCite,
}: {
  children: string;
  onCite?: (n: number) => void;
}) {
  const cite = onCite
    ? {
        p: ({ children: inner }: { children?: ReactNode }) => <p>{withCitations(inner, onCite)}</p>,
        li: ({ children: inner }: { children?: ReactNode }) => <li>{withCitations(inner, onCite)}</li>,
      }
    : undefined;

  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={cite}
      >
        {normalizeMath(children)}
      </ReactMarkdown>
    </div>
  );
}
