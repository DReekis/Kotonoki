import html
import re

try:
    import nh3
except ImportError:
    nh3 = None

try:
    import bleach
except ImportError:
    bleach = None

# Strictly allowed HTML tags for the WordPad-style rich-text editor
ALLOWED_TAGS = {
    "p",
    "strong",
    "em",
    "u",
    "mark",
    "blockquote",
    "a",
    "br"
}

ALLOWED_ATTRIBUTES = {
    "a": {"href"}
}

ALLOWED_URL_SCHEMES = {
    "http",
    "https"
}

class SanitizerService:
    @staticmethod
    def sanitize_html(raw_html: str) -> str:
        """
        Sanitize HTML to conform to the strict WordPad-like allowlist.
        Strips all scripts, styles, iframes, inline event handlers, and dangerous URL protocols.
        Injects rel="noopener noreferrer" on all links.
        """
        if not raw_html:
            return ""

        if nh3 is not None:
            cleaned = nh3.clean(
                raw_html,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                url_schemes=ALLOWED_URL_SCHEMES,
                link_rel="noopener noreferrer"
            )
            return cleaned.strip()
        elif bleach is not None:
            cleaned = bleach.clean(
                raw_html,
                tags=list(ALLOWED_TAGS),
                attributes=ALLOWED_ATTRIBUTES,
                protocols=list(ALLOWED_URL_SCHEMES),
                strip=True
            )
            return cleaned.strip()
        else:
            return html.escape(raw_html)

    @staticmethod
    def extract_text_excerpt(html_content: str, max_length: int = 240) -> str:
        """
        Extract clean, tag-free text excerpt for cards and RSS/meta tags.
        """
        if not html_content:
            return ""

        if nh3 is not None:
            text = nh3.clean_text(html_content)
        elif bleach is not None:
            text = bleach.clean(html_content, tags=[], strip=True)
        else:
            text = re.sub(r"<[^>]+>", "", html_content)

        text = " ".join(text.split())
        if len(text) <= max_length:
            return text
        return text[:max_length].rstrip() + "…"
