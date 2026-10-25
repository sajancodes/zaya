"""Notify the official catalog using the release job's short-lived GitHub identity."""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = 'https://zayaxyz.vercel.app/api/internal/releases/sync'


def sync(tag):
    url = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    url += ('&' if '?' in url else '?') + urllib.parse.urlencode({'audience':ENDPOINT})
    request = urllib.request.Request(url, headers={'Authorization':'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with urllib.request.urlopen(request, timeout=15) as response:
        identity = json.loads(response.read(20000))['value']
    request = urllib.request.Request(ENDPOINT, data=json.dumps({'tag':tag}).encode(),
                                     headers={'Content-Type':'application/json', 'Authorization':'Bearer ' + identity}, method='POST')
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.loads(response.read(20000))
        if data.get('status') != 'ok' or not data.get('releases'):
            raise RuntimeError('Catalog did not confirm verified release metadata')
    print('Official release catalog synchronization confirmed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    try:
        sync(args.tag)
    except Exception:
        # Never print tokens, authorization headers, request objects or responses.
        raise SystemExit('Release was published, but catalog sync failed. Retry the authenticated synchronization; do not overwrite immutable assets.') from None
