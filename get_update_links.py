import json
from pathlib import Path

from utils.get_list_of_updates import main as get_list_of_updates
from utils.get_update_from_update_catalog import get_update_from_update_catalog


def get_update_url(arch: str, windows_version: str, update_kb: str):
    url = get_update_from_update_catalog(arch, windows_version, update_kb)
    if url:
        return url

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
                    if arch in links:
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
