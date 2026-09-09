"""Read-only post-deployment check of public HTML, assets and legacy CORS."""
import json
import re
import urllib.request
from urllib.parse import urljoin


def check_entrypoints():
    for entrypoint in [
        'https://app.pasekaproduction.ru:9443/',
        'https://app.pasekaproduction.ru/',
        'https://your-body-pro.vercel.app/',
        'https://api.pasekaproduction.ru/yourbody-app/',
        'https://api.pasekaproduction.ru/yourbody-app/admin/console?probe=entrypoint',
    ]:
        request = urllib.request.Request(entrypoint, headers={'Accept': 'text/html'})
        with urllib.request.urlopen(request, timeout=20) as response:
            body, final_url = response.read(), response.url
        if '/admin/console' in entrypoint:
            assert final_url.endswith('/admin/console?probe=entrypoint'), final_url
        assets = [item.decode() for item in re.findall(rb'(?:src|href)="([^" ]+\.(?:js|css))"', body) if item.startswith(b'/assets/')]
        assert assets, f'No application assets in {entrypoint}'
        for asset in assets:
            with urllib.request.urlopen(urljoin(final_url, asset), timeout=20) as response:
                expected = 'javascript' if asset.endswith('.js') else 'text/css'
                assert expected in response.headers.get('Content-Type', ''), f'Invalid asset type: {asset}'
        print(json.dumps({'entrypoint': entrypoint, 'final_url': final_url, 'assets_ok': len(assets)}))
    request = urllib.request.Request('https://api.pasekaproduction.ru/yourbody/api/me', method='OPTIONS', headers={
        'Origin': 'https://your-body-pro.vercel.app', 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'content-type,x-telegram-init-data',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        assert response.headers.get('Access-Control-Allow-Origin') == 'https://your-body-pro.vercel.app'
    print('Legacy CORS: OK')


if __name__ == '__main__':
    check_entrypoints()
