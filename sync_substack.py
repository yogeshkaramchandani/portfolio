#!/usr/bin/env python3
"""Adds new Substack posts (from your public RSS feed) to projects.json."""
import json, re, html, urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime

OK = {'p','h2','h3','ul','ol','li','blockquote','a','strong','b','em','i','br','hr','pre','code','img','figure','figcaption'}
MAP = {'h1':'h2','h2':'h2','h3':'h3','h4':'h3','h5':'h3','h6':'h3'}
VOID = {'br','hr','img'}
SKIP = ('subscription-widget','button-wrapper','captioned-button','share-button','footnote-anchor')

class Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.out=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.skip:
            if tag not in VOID: self.skip += 1
            return
        if tag in ('script','style') or any(k in (a.get('class') or '') for k in SKIP):
            if tag not in VOID: self.skip = 1
            return
        tag = MAP.get(tag, tag)
        if tag not in OK: return
        if tag == 'a':
            h = a.get('href') or ''
            if re.match(r'https?://|mailto:', h):
                self.out.append('<a href="%s" target="_blank" rel="noopener noreferrer">' % html.escape(h, True))
            else:
                self.out.append('<a>')
        elif tag == 'img':
            s = a.get('src') or ''
            if s.startswith('https://'):
                self.out.append('<img src="%s" alt="%s" loading="lazy">' % (html.escape(s, True), html.escape(a.get('alt') or '', True)))
        else:
            self.out.append('<%s>' % tag)
    def handle_startendtag(self, tag, attrs): self.handle_starttag(tag, attrs)
    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1; return
        tag = MAP.get(tag, tag)
        if tag in OK and tag not in VOID: self.out.append('</%s>' % tag)
    def handle_data(self, d):
        if not self.skip: self.out.append(html.escape(d, quote=False))

def parse(xml):
    root = ET.fromstring(xml); out = []
    for it in root.iter('item'):
        link = (it.findtext('link') or '').strip()
        if not link: continue
        raw = it.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or ''
        c = Clean(); c.feed(raw)
        body = re.sub(r'<p>\s*</p>', '', ''.join(c.out))
        desc = re.sub(r'<[^>]+>', '', html.unescape(it.findtext('description') or '')).strip()
        enc = it.find('enclosure'); img = (enc.get('url') if enc is not None else '') or ''
        if not img:
            m = re.search(r'<img src="(https://[^"]+)"', body)
            img = html.unescape(m.group(1)) if m else ''
        try: date = parsedate_to_datetime(it.findtext('pubDate')).date().isoformat()
        except Exception: date = ''
        slug = re.sub(r'[^a-z0-9-]', '', link.rstrip('/').split('/')[-1].lower())[:60]
        out.append({'id':'ss-'+slug,'title':(it.findtext('title') or '').strip(),'date':date,'summary':desc,
                    'body':'','html':body,'image':img,'pdf':'','link':link,'source':'substack'})
    return out

def main():
    D = json.load(open('projects.json', encoding='utf-8'))
    base = (D.get('site', {}).get('substack') or '').strip().rstrip('/')
    if not base:
        print('No Substack address set in Admin > Site details'); return
    if not base.startswith('http'): base = 'https://' + base
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://google.com/'
    }
    proxy_url = 'https://api.allorigins.win/raw?url=' + base + '/feed'
    req = urllib.request.Request(proxy_url, headers=headers)    
    posts = parse(urllib.request.urlopen(req, timeout=30).read())
    hidden = set(D.get('hidden', [])); have = {p['id']: i for i, p in enumerate(D['projects'])}; changed = False
    for r in posts:
        if r['id'] in hidden: continue
        if r['id'] in have:
            i = have[r['id']]
            if D['projects'][i].get('source') == 'substack' and D['projects'][i] != r:
                D['projects'][i] = r; changed = True
        else:
            D['projects'].append(r); changed = True
    if changed:
        D['projects'].sort(key=lambda p: p.get('date', ''), reverse=True)
        json.dump(D, open('projects.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print('projects.json updated')
    else:
        print('Nothing new')

if __name__ == '__main__':
    main()
