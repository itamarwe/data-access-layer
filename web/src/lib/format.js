import { escapeHtml } from "./html.js";

export function label(value) {
  return String(value).replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

// Render a small Markdown subset. Source HTML is always text, never executable markup.
export function inline(text) {
  const tokens = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\([^\s)]+\))/g;
  return String(text).split(tokens).map((part) => {
    if (part.startsWith("`") && part.endsWith("`")) return `<code>${escapeHtml(part.slice(1, -1))}</code>`;
    if (part.startsWith("**") && part.endsWith("**")) return `<strong>${escapeHtml(part.slice(2, -2))}</strong>`;
    if (part.startsWith("*") && part.endsWith("*")) return `<em>${escapeHtml(part.slice(1, -1))}</em>`;
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link && /^https?:\/\//i.test(link[2])) {
      return `<a href="${escapeHtml(link[2])}" target="_blank" rel="noopener noreferrer">${escapeHtml(link[1])}</a>`;
    }
    return escapeHtml(part);
  }).join("");
}

export function markdown(text) {
  const lines = String(text ?? "").replaceAll("\r\n", "\n").split("\n");
  const blocks = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (/^\s*```/.test(line)) {
      const code = [];
      const language = line.trim().slice(3).trim();
      for (i++; i < lines.length && !/^\s*```/.test(lines[i]); i++) code.push(lines[i]);
      i++;
      blocks.push(language === "sql" ? sqlBlock(code.join("\n")) : `<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = Math.min(6, heading[1].length + 2);
      blocks.push(`<h${level}>${inline(heading[2])}</h${level}>`); i++; continue;
    }
    if (line.includes("|") && /^\s*\|?\s*:?-{3,}.*\|/.test(lines[i + 1] || "")) {
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
      const head = cells(line);
      const body = [];
      for (i += 2; i < lines.length && lines[i].includes("|") && lines[i].trim(); i++) {
        body.push(`<tr>${cells(lines[i]).map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`);
      }
      blocks.push(`<div class="table-scroll"><table class="data-table"><thead><tr>${head.map((cell) => `<th scope="col">${inline(cell)}</th>`).join("")}</tr></thead><tbody>${body.join("")}</tbody></table></div>`);
      continue;
    }
    const list = line.match(/^\s*(?:([-*])|\d+[.)])\s+(.+)$/);
    if (list) {
      const tag = list[1] ? "ul" : "ol";
      const items = [];
      const pattern = list[1] ? /^\s*[-*]\s+(.+)$/ : /^\s*\d+[.)]\s+(.+)$/;
      while (i < lines.length && pattern.test(lines[i])) items.push(`<li>${inline(lines[i++].match(pattern)[1])}</li>`);
      blocks.push(`<${tag}>${items.join("")}</${tag}>`); continue;
    }
    if (/^>\s?/.test(line)) {
      const quote = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^>\s?/, ""));
      blocks.push(`<blockquote>${inline(quote.join("\n"))}</blockquote>`); continue;
    }
    const paragraph = [line]; i++;
    while (i < lines.length && lines[i].trim() && !/^\s*(#|```|>|[-*] |\d+[.)] )/.test(lines[i])) {
      if (lines[i].includes("|") && /^\s*\|?\s*:?-{3,}.*\|/.test(lines[i + 1] || "")) break;
      paragraph.push(lines[i++]);
    }
    blocks.push(`<p>${inline(paragraph.join("\n"))}</p>`);
  }
  return `<div class="prose">${blocks.join("")}</div>`;
}

export function sqlBlock(sql) {
  const tokens = /(--[^\n]*|\/\*[\s\S]*?\*\/|'(?:''|[^'])*'|"(?:""|[^"])*"|\b(?:select|from|where|join|left|right|inner|outer|full|cross|on|as|with|and|or|not|null|is|in|exists|group|by|order|having|limit|offset|union|all|distinct|case|when|then|else|end|over|partition|asc|desc|true|false)\b)/gi;
  const highlighted = String(sql).split(tokens).map((part, index) => {
    if (index % 2 === 0) return escapeHtml(part);
    const kind = part.startsWith("--") || part.startsWith("/*") ? "comment" : /^["']/.test(part) ? "string" : "keyword";
    return `<span class="sql-${kind}">${escapeHtml(part)}</span>`;
  }).join("");
  return `<pre class="sql-block"><code>${highlighted}</code></pre>`;
}

export function valueView(value) {
  if (value === null || value === undefined) return '<span class="quiet-empty">Not recorded</span>';
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? `<ul class="value-list">${value.map((item) => `<li>${valueView(item)}</li>`).join("")}</ul>` : '<span class="quiet-empty">None</span>';
  if (typeof value === "object") return `<dl class="fact-list">${Object.entries(value).map(([key, item]) => `<div><dt>${escapeHtml(label(key))}</dt><dd>${valueView(item)}</dd></div>`).join("")}</dl>`;
  return `<span class="text-value">${escapeHtml(value)}</span>`;
}
