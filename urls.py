"""URL helpers for rejecting non-http(s) schemes."""
from urllib.parse import urlparse


def safe_http_url(url):
    """Return url if it is http(s) with a host; otherwise None."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return url
    return None
