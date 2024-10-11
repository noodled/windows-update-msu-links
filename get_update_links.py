import functools
import json
import re
import time
from pathlib import Path

import requests

from utils.get_list_of_updates import main as get_list_of_updates
from utils.get_update_from_update_catalog import get_update_from_update_catalog

session = requests.Session()


@functools.lru_cache(maxsize=100)
def get_page_html(url: str):
    while True:
        try:
            response = session.get(url)
            response.raise_for_status()
            break
        except Exception as e:
            print(f'Failed to get {url}, retrying...')
            print(f'       {e}')
            time.sleep(10)

    return response.text


def get_update_url_from_deskmodder_post(blog_post_url: str, arch: str, update_kb: str):
    html = get_page_html(blog_post_url)

    match = re.search(
        rf'\bhttps?://[^/]*\.(?:windowsupdate|microsoft)\.com/\S*?/windows[^-]*-{re.escape(update_kb.lower())}-{re.escape(arch.lower())}_\S*?\.(?:msu|cab)\b',
        html,
    )
    if match:
        return match.group(0)

    # if re.search(
    #     rf'{re.escape(update_kb)}[-_]{re.escape(arch)}', html, flags=re.IGNORECASE
    # ):
    #     print(f'Unsupported format? Found {update_kb} in {blog_post_url}')

    return None


def get_update_url_deskmodder(arch: str, update_kb: str):
    search_url = f'https://www.deskmodder.de/blog/?s={update_kb}'

    html = get_page_html(search_url)

    results = re.findall(
        r'<h2 class="entry-title">\s*<a href="(https://www.deskmodder.de/blog/[^"]*)"',
        html,
    )

    for result in results:
        url = get_update_url_from_deskmodder_post(result, arch, update_kb)
        if url:
            return url

    return None


def get_update_url(arch: str, windows_version: str, update_kb: str):
    url = get_update_from_update_catalog(arch, windows_version, update_kb)
    if url:
        return url

    # url = get_update_url_deskmodder(arch, update_kb)
    # if url:
    #     return url

    # TODO: more sources?

    return None


def main():
    get_list_of_updates()

    updates_path = Path('updates.json')
    with updates_path.open() as f:
        updates = json.load(f)

    update_links_path = Path('update_links.json')
    with update_links_path.open() as f:
        update_links = json.load(f)

    try:
        for windows_version in updates:
            for update_kb in updates[windows_version]:
                date = updates[windows_version][update_kb]['releaseDate']
                has_no_arm64 = windows_version in {'1507', '1511', '1607', '1703'} or (
                    windows_version == '1809' and date >= '2024-07-09'
                )

                if windows_version.startswith('11-'):
                    archs = ['x64']
                else:
                    archs = ['x86', 'x64']

                if not has_no_arm64:
                    archs.append('arm64')

                for arch in archs:
                    links = update_links.setdefault(windows_version, {}).setdefault(
                        update_kb, {}
                    )
                    if links.get(arch):
                        continue

                    url = get_update_url(arch, windows_version, update_kb)
                    links[arch] = url
                    print(f'{windows_version}-{update_kb}-{arch}: {url}')
    except KeyboardInterrupt:
        print('Interrupted...')

    with update_links_path.open('w') as f:
        json.dump(update_links, f, indent=2)


if __name__ == "__main__":
    main()
