"""Read only publicly accessible publisher text; obey robots and paywall signals."""
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

AGENT = 'WapitiBugle'


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocked = 0
        self.article = 0
        self.paragraph = 0
        self.parts = []
        self.description = ''
        self.paywall = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside'):
            self.blocked += 1
        if tag == 'article':
            self.article += 1
        if tag == 'p':
            self.paragraph += 1
        if tag == 'meta' and attrs.get('property', attrs.get('name', '')) in ('og:description', 'description'):
            self.description = attrs.get('content', '')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'footer', 'header', 'aside'):
            self.blocked = max(0, self.blocked - 1)
        if tag == 'article':
            self.article = max(0, self.article - 1)
        if tag == 'p':
            self.paragraph = max(0, self.paragraph - 1)
            self.parts.append('\n')

    def handle_data(self, data):
        if self.article and self.paragraph and not self.blocked:
            self.parts.append(data)

    def result(self):
        body = re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()
        return body[:7000] if len(body) >= 400 else ''


class Reader:
    def __init__(self, feeds):
        self.hosts = {h for f in feeds for h in f['hosts']}
        self.robots = {}

    def allowed_url(self, url):
        try:
            parsed = urllib.parse.urlsplit(url)
            return parsed.scheme == 'https' and not parsed.username and not parsed.password and parsed.port in (None, 443) and parsed.hostname and any(parsed.hostname == h or parsed.hostname.endswith('.' + h) for h in self.hosts)
        except ValueError:
            return False

    def read(self, url):
        if not self.allowed_url(url):
            return ''
        reader = self
        class PublisherRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                if not reader.allowed_url(newurl):
                    raise ValueError('Non-publisher redirect')
                return super().redirect_request(req, fp, code, msg, headers, newurl)
        opener = urllib.request.build_opener(PublisherRedirect)
        origin = urllib.parse.urlsplit(url)
        origin = origin.scheme + '://' + origin.netloc
        try:
            if origin not in self.robots:
                try:
                    with opener.open(urllib.request.Request(origin + '/robots.txt', headers={'User-Agent': AGENT}), timeout=5) as response:
                        raw = response.read(200_001)
                    if len(raw) > 200_000:
                        return ''
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(raw.decode('utf-8', 'replace').splitlines())
                    self.robots[origin] = parser
                except urllib.error.HTTPError as error:
                    if error.code == 404:
                        self.robots[origin] = True
                    else:
                        self.robots[origin] = False
            robots = self.robots[origin]
            if robots is False or (robots is not True and not robots.can_fetch(AGENT, url)):
                return ''
            with opener.open(urllib.request.Request(url, headers={'User-Agent': AGENT + '/1.0 (+https://wapitibugle.com)'}), timeout=8) as response:
                if 'html' not in response.headers.get('Content-Type', ''):
                    return ''
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                return ''
            page = raw.decode('utf-8', 'replace')
            if re.search(r'"isAccessibleForFree"\s*:\s*(false|"false")', page, re.I):
                return ''
            parser = ArticleText()
            parser.feed(page)
            return parser.result()
        except Exception:
            return ''
