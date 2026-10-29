/**
 * Renders the bot's Telegram HTML as Telegram would: <b>, <i>, <code>, <a> and line breaks.
 *
 * The shots are not retyped. scripts/export_shots.py runs the real reply functions and writes
 * shots.json; this turns that markup into spans, so a wording change in the bot is a re-render
 * here and never a screenshot somebody has to retake.
 */
import React from 'react';
import {Code, Link} from './telegram';

type Node = string | {tag: string; children: Node[]};

const ENTITIES: Record<string, string> = {
  '&lt;': '<',
  '&gt;': '>',
  '&amp;': '&',
  '&quot;': '"',
  '&#x27;': "'",
};
const decode = (s: string) => s.replace(/&(lt|gt|amp|quot|#x27);/g, (m) => ENTITIES[m] ?? m);

function parse(html: string): Node[] {
  const root: {tag: string; children: Node[]} = {tag: 'root', children: []};
  const stack = [root];
  const re = /<\/?([a-z]+)[^>]*>|[^<]+/g;
  for (const m of html.matchAll(re)) {
    const top = stack[stack.length - 1]!;
    if (!m[1]) {
      top.children.push(decode(m[0]));
    } else if (m[0].startsWith('</')) {
      if (stack.length > 1) stack.pop();
    } else {
      const node = {tag: m[1], children: [] as Node[]};
      top.children.push(node);
      stack.push(node);
    }
  }
  return root.children;
}

function render(nodes: Node[], key = ''): React.ReactNode[] {
  return nodes.map((n, i) => {
    const k = `${key}${i}`;
    if (typeof n === 'string') {
      const lines = n.split('\n');
      return lines.flatMap((line, j) => (j ? [<br key={`${k}-${j}`} />, line] : [line]));
    }
    const inner = render(n.children, `${k}-`);
    switch (n.tag) {
      case 'b':
        return (
          <b key={k} style={{fontWeight: 700}}>
            {inner}
          </b>
        );
      case 'i':
        return (
          <i key={k} style={{color: '#B9C6D2'}}>
            {inner}
          </i>
        );
      case 'code':
        return <Code key={k}>{inner}</Code>;
      case 'a':
        return <Link key={k}>{inner}</Link>;
      default:
        return <React.Fragment key={k}>{inner}</React.Fragment>;
    }
  });
}

// Telegram keeps runs of spaces (the replies indent detail lines), so the browser must too.
export const TgHtml: React.FC<{html: string}> = ({html}) => (
  <span style={{whiteSpace: 'pre-wrap'}}>{render(parse(html))}</span>
);
