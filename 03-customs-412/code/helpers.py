"""Site-local HTML and protocol-cookie helpers."""
import time
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'


def apply_cookie_writes(session, writes, url):
    """Apply document.cookie writes without replacing HttpOnly server cookies."""
    host = urlsplit(url).hostname
    for raw in writes:
        parsed = SimpleCookie()
        parsed.load(raw)
        if not parsed:
            raise ValueError('Malformed JavaScript cookie write')
        for name, item in parsed.items():
            domain = item['domain'] or host
            path = item['path'] or '/'
            if domain.lstrip('.') != host:
                raise ValueError('Unexpected cookie domain')
            if any(c.name == name and c.has_nonstandard_attr('HttpOnly') for c in session.cookies):
                raise ValueError('JavaScript attempted to overwrite an HttpOnly cookie')
            expires = None
            if item['max-age']:
                expires = int(time.time()) + int(item['max-age'])
            elif item['expires']:
                expires = int(parsedate_to_datetime(item['expires']).timestamp())
            if expires is not None and expires <= time.time():
                for c in list(session.cookies):
                    if c.name == name and c.domain.lstrip('.') == domain.lstrip('.') and c.path == path:
                        session.cookies.clear(c.domain,c.path,c.name)
                continue
            session.cookies.set(name,item.value,domain=domain,path=path,secure=bool(item['secure']),expires=expires,rest={})



class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.scripts, self.metas, self.links = [], [], []
        self.active = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.active = dict(attrs, code='')
            self.scripts.append(self.active)
        elif tag == 'meta':
            self.metas.append(attrs)
        elif tag in ('a', 'iframe'):
            self.links.append(attrs)

    def handle_data(self, data):
        if self.active is not None:
            self.active['code'] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = None
