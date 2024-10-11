import functools
import json
import re
import time
from pathlib import Path
from typing import Optional

import requests
from frozendict import frozendict

from utils.get_list_of_updates import main as get_list_of_updates
from utils.get_update_from_update_catalog import get_update_from_update_catalog

session = requests.Session()


# https://stackoverflow.com/a/53394430
def freezeargs(func):
    """Convert a mutable dictionary into immutable.
    Useful to be compatible with cache
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        args = (frozendict(arg) if isinstance(arg, dict) else arg for arg in args)
        kwargs = {
            k: frozendict(v) if isinstance(v, dict) else v for k, v in kwargs.items()
        }
        return func(*args, **kwargs)

    return wrapped


def get_update_url_from_text(text: str, arch: str, update_kb: str):
    match = re.findall(
        rf'\bhttps?://[^/]*\.(?:windowsupdate|microsoft)\.com/\S*?/windows[^-]*-{re.escape(update_kb.lower())}-{re.escape(arch.lower())}_\S*?\.msu\b',
        text,
    )
    if match:
        results = set(match)

        if len(results) > 1:
            results_no_delta = [x for x in results if '_delta_' not in x]
            if len(results_no_delta) == 1:
                results = results_no_delta

        if len(results) == 1:
            url = results.pop()
            url = re.sub(r'^https?://', 'https://', url)
            url = re.sub(
                r'^https://download\.windowsupdate\.com/',
                'https://catalog.s.download.windowsupdate.com/',
                url,
            )
            return url

        print(f'> Found multiple results for {update_kb}-{arch}')
    else:
        if re.search(
            rf'{re.escape(update_kb)}[-_]{re.escape(arch)}', text, flags=re.IGNORECASE
        ):
            print(f'> Unsupported format? Found {update_kb}-{arch}')

    return None


@freezeargs
@functools.lru_cache(maxsize=100)
def get_page_html(url: str, cookies: Optional[dict] = None):
    while True:
        try:
            response = session.get(url, cookies=cookies)
            response.raise_for_status()
            break
        except Exception as e:
            print(f'Failed to get {url}, retrying...')
            print(f'       {e}')
            time.sleep(10)

    return response.text


def get_update_url_from_deskmodder_post(blog_post_url: str, arch: str, update_kb: str):
    html = get_page_html(blog_post_url)

    return get_update_url_from_text(html, arch, update_kb)


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


def get_update_url_from_windowsphoneinfo_post(
    blog_post_url: str, arch: str, update_kb: str, cookies: dict
):
    cookies = {
        'xf_user': '',
        'xf_session': '',
    }

    html = get_page_html(blog_post_url, cookies=cookies)

    return get_update_url_from_text(html, arch, update_kb)


def get_update_url_windowsphoneinfo(arch: str, update_kb: str):
    cookies = {
        'xf_user': '',
        'xf_session': '',
    }

    html = requests.get('https://www.windowsphoneinfo.com', cookies=cookies).text
    xf_token = re.findall(r'_csrfToken: "(.*?)"', html)[0]

    search_url = f'https://www.windowsphoneinfo.com/search/search'
    params = {
        'keywords': update_kb,
        'users': '',
        'date': '',
        '_xfToken': xf_token,
    }
    html = requests.post(search_url, params=params, cookies=cookies).text

    results = re.findall(
        r'<h3 class="title"><a href="(threads/[^"]*)"',
        html,
    )

    for result in results:
        url = get_update_url_from_windowsphoneinfo_post(
            'https://www.windowsphoneinfo.com/' + result, arch, update_kb, cookies
        )
        if url:
            return url

    return None


def get_update_url_from_jsb000_post(blog_post_url: str, arch: str, update_kb: str):
    html = get_page_html(blog_post_url)

    return get_update_url_from_text(html, arch, update_kb)


def get_update_url_jsb000(arch: str, update_kb: str):
    search_url = f'https://jsb000.tistory.com/search/{update_kb}'

    html = get_page_html(search_url)

    start = html.find('<div id="body"')
    assert start > 0
    html = html[start:]

    end = html.find('<div id="paging"')
    assert end > 0
    html = html[:end]

    results = re.findall(
        r'<a href="(/[^"]*)"',
        html,
    )

    for result in results:
        url = get_update_url_from_jsb000_post('https://jsb000.tistory.com' + result, arch, update_kb)
        if url:
            return url

    return None


# mydigitallife = Path('mydigitallife.txt').read_text(encoding='utf-8')
# mydigitallife = mydigitallife.splitlines()
# mydigitallife = [x.lower() for x in mydigitallife if 'http' in x.lower()]
# mydigitallife = '\n'.join(mydigitallife)


def get_update_url(arch: str, windows_version: str, update_kb: str):
    url = get_update_url_jsb000(arch, update_kb)
    if url:
        return url

    # url = get_update_url_from_text(mydigitallife, arch, update_kb)
    # if url:
    #     return url

    # url = get_update_from_update_catalog(arch, windows_version, update_kb)
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
