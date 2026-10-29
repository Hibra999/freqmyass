"""Fetch the requested originals, record exact provenance, then apply documented import-only fixes."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.catalog import ROOT, STRATEGIES, STRATEGY_INFO, initialize, write_json


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'FreqMyAss-installer'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main():
    initialize()
    lock_path = ROOT / 'strategies.lock.json'
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    for item in STRATEGY_INFO:
        name = item['name']
        entry = lock.get(name)
        revision = entry['revision'] if entry else json.loads(fetch(
            f"https://api.github.com/repos/{item['repo']}/commits/{item['branch']}"))['sha']
        url = f"https://raw.githubusercontent.com/{item['repo']}/{revision}/{item['path']}"
        source = fetch(url)
        digest = hashlib.sha256(source).hexdigest()
        if entry and entry['sha256'] != digest:
            raise ValueError(f'Integrity check failed: {name}')
        originals = STRATEGIES.parent / 'originals'
        originals.mkdir(exist_ok=True)
        (originals / f'{name}.py').write_bytes(source)
        text = source.decode('utf-8-sig')
        # pandas_ta is imported but unused by dip_catcher; avoid an unnecessary dependency.
        if name == 'dip_catcher':
            text = '\n'.join(line for line in text.splitlines() if not line.startswith('import pandas_ta')) + '\n'
        (STRATEGIES / f'{name}.py').write_text(text, encoding='utf-8')
        lock[name] = dict(url=url, revision=revision, sha256=digest)
        print(f'{name}: source verified ({revision[:12]})')
    write_json(lock_path, lock)


if __name__ == '__main__':
    main()
