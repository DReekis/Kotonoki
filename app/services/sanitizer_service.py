import nh3

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

        cleaned = nh3.clean(
            raw_html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            url_schemes=ALLOWED_URL_SCHEMES,
            link_rel="noopener noreferrer"
        )
        return cleaned.strip()

    @staticmethod
    def extract_text_excerpt(html_content: str, max_length: int = 240) -> str:
        """
        Extract clean, tag-free text excerpt for cards and RSS/meta tags.
        """
        text = nh3.clean_text(html_content or "")
        text = " ".join(text.split())
        if len(text) <= max_length:
            return text
        return text[:max_length].rstrip() + "…"
