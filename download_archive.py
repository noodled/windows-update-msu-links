import requests

session = requests.Session()

cookies = {
    'xf_user': '',
    'xf_session': '',
    'cf_clearance': '',
}

with open("mydigitallife.txt", "w", encoding="utf-8") as f:
    for i in range(0, 747):
        print(f"page {i+1}")

        url = f"https://forums.mydigitallife.net/threads/windows-10-hotfix-repository.57050/page-{i+1}"

        html = session.get(url, cookies=cookies).text

        f.write(html)
        f.write("\n")
