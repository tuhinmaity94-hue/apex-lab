"""Download pinned browser libraries and original wiki weapon renders.
Run once during setup. Runtime never depends on a CDN.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import hashlib
import json
import re
import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'frontend' / 'assets'
VENDOR = ROOT / 'frontend' / 'vendor'
HEADERS = {'User-Agent': 'ApexLabCourseProject/1.0 (educational local archive)'}
WEAPONS = {
    'r301': 'R-301_Carbine', 'flatline': 'VK-47_Flatline',
    'r99': 'R-99_SMG', 'volt': 'Volt_SMG', 'alternator': 'Alternator_SMG',
    'car': 'C.A.R._SMG', 'wingman': 'Wingman', 'mastiff': 'Mastiff_Shotgun',
    'spitfire': 'M600_Spitfire', 'prowler': 'Prowler_Burst_PDW',
    'sheila': 'Sheila', 'devotion': 'Devotion_LMG', 'havoc': 'HAVOC_Rifle',
    'eva8': 'EVA-8_Auto', 'mozambique': 'Mozambique_Shotgun',
    'nemesis': 'Nemesis_Burst_AR', 'p2020': 'P2020', 'rampage': 'Rampage_LMG',
    'lstar': 'L-STAR_EMG', 're45': 'RE-45_Auto', 'hemlok': 'Hemlok_Burst_AR',
    'repeater': '30-30_Repeater', 'g7': 'G7_Scout', 'bocek': 'Bocek_Compound_Bow',
    'triple-take': 'Triple_Take', 'peacekeeper': 'Peacekeeper',
    'kraber': 'Kraber_.50-Cal_Sniper', 'longbow': 'Longbow_DMR',
    'charge-rifle': 'Charge_Rifle', 'vantage': "Vantage/Sniper's_Mark",
    'sentinel': 'Sentinel',
}
FILE_TITLES = {
    'sheila': 'Mobile_Minigun_%22Sheila%22',
    'vantage': 'A-13_Sentry',
}


def download(url, dest):
    r = requests.get(url, timeout=40, headers=HEADERS)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return hashlib.sha256(r.content).hexdigest()


def weapon(item):
    slug, title = item
    page = 'https://apexlegends.wiki.gg/wiki/' + title
    r = requests.get(page, timeout=40, headers=HEADERS)
    r.raise_for_status()
    matches = re.findall(r'<img\b[^>]*>', r.text)
    selected = None
    for tag in matches:
        alt = re.search(r'alt="([^"]*)"', tag)
        src = re.search(r'\bsrc="([^"]*)"', tag)
        if alt and src and '.png' in alt.group(1) and 'Icon' not in alt.group(1) and '/images/' in src.group(1):
            selected = urljoin(page, src.group(1).replace('&amp;', '&'))
            break
    dest = ASSETS / (slug + '.png')
    if dest.exists():
        recorded = ASSETS / (slug + '.source.txt')
        if recorded.exists():
            selected = recorded.read_text(encoding='utf-8').strip()
        if not selected:
            raise RuntimeError('No weapon render: ' + title)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    else:
        file_names = [FILE_TITLES.get(slug), title.split('/')[-1], title]
        original = None
        file_page = page
        for name in file_names:
            if not name:
                continue
            file_page = 'https://apexlegends.wiki.gg/wiki/File:' + name + '.png'
            file_response = requests.get(file_page, timeout=40, headers=HEADERS)
            if file_response.status_code == 404:
                continue
            file_response.raise_for_status()
            original = re.search(r'href="(/images/(?!thumb/)[^"]+\.png[^"]*)"', file_response.text)
            if original:
                break
        if original:
            selected = urljoin(file_page, original.group(1).replace('&amp;', '&'))
        if not selected:
            raise RuntimeError('No weapon render: ' + title)
        digest = download(selected, dest)
    (ASSETS / (slug + '.source.txt')).write_text(selected, encoding='utf-8')
    return {'slug': slug, 'page': page, 'image_url': selected, 'sha256': digest,
            'attribution': 'Apex Legends Wiki / EA / Respawn. Game imagery belongs to its respective owners.'}


if __name__ == '__main__':
    ASSETS.mkdir(exist_ok=True)
    VENDOR.mkdir(exist_ok=True)
    libs = [
        ('https://cdn.jsdelivr.net/npm/vue@3.5.22/dist/vue.global.prod.js', 'vue.global.prod.js'),
        ('https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js', 'echarts.min.js'),
        ('https://cdn.jsdelivr.net/npm/vue@3.5.22/LICENSE', 'VUE-LICENSE.txt'),
        ('https://cdn.jsdelivr.net/npm/echarts@5.6.0/LICENSE', 'ECHARTS-LICENSE.txt'),
    ]
    for url, name in libs:
        if not (VENDOR / name).exists():
            download(url, VENDOR / name)
        print('Saved', name, flush=True)
    results = [weapon(item) for item in WEAPONS.items()]
    (ASSETS / 'sources.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Saved', len(results), 'weapon images', flush=True)
