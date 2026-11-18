import privacyPolicy from "../../docs/PRIVACY_POLICY.md?raw";
import termsOfService from "../../docs/TERMS_OF_SERVICE.md?raw";
import cookiePolicy from "../../docs/COOKIE_POLICY.md?raw";
import securityAudit from "../../docs/SECURITY_AUDIT.md?raw";

const documents = {
  privacy: { title: "Privacy policy", source: privacyPolicy },
  terms: { title: "Terms of use", source: termsOfService },
  cookies: { title: "Cookie policy", source: cookiePolicy },
  security: { title: "Security audit guide", source: securityAudit },
};

function InlineText({ text }) {
  // Markdown is parsed into React text nodes; repository text is never HTML.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return <span key={index}>{part}</span>;
  });
}

function MarkdownDocument({ source }) {
  const lines = source.split(/\r?\n/);
  const blocks = [];
  let paragraph = [];
  let list = [];
  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: "p", text: paragraph.join(" ") });
    paragraph = [];
  };
  const flushList = () => {
    if (list.length) blocks.push({ type: "ul", items: list });
    list = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
    } else if (line.startsWith("# ") || line.startsWith("## ") || line.startsWith("### ")) {
      flushParagraph();
      flushList();
      const depth = line.startsWith("### ") ? 3 : line.startsWith("## ") ? 2 : 1;
      blocks.push({ type: `h${depth}`, text: line.replace(/^#{1,3}\s+/, "") });
    } else if (line.startsWith("- ")) {
      flushParagraph();
      list.push(line.slice(2));
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();

  return blocks.map((block, index) => {
    if (block.type === "ul") {
      return <ul key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}><InlineText text={item} /></li>)}</ul>;
    }
    const Tag = block.type;
    return <Tag key={index}><InlineText text={block.text} /></Tag>;
  });
}

export function PolicyModal({ name, onClose }) {
  const document = documents[name];
  if (!document) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="document-dialog" role="dialog" aria-modal="true" aria-labelledby="document-title">
        <div className="dialog-heading">
          <div><p className="section-label">DOCUGUARD INFORMATION</p><h2 id="document-title">{document.title}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close document">×</button>
        </div>
        <article className="policy-copy"><MarkdownDocument source={document.source} /></article>
      </section>
    </div>
  );
}
