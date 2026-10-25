"""Trust only this private repository's release job, using GitHub's signed OIDC."""
from functools import lru_cache
import re

ISSUER = 'https://token.actions.githubusercontent.com'
AUDIENCE = 'https://zayaxyz.vercel.app/api/internal/releases/sync'
REPOSITORY = 'sajancodes/zaya'
REPOSITORY_ID = '1418551108'
OWNER_ID = '167339084'
TAG = re.compile(r'v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?')


@lru_cache(maxsize=1)
def _keys():
    import jwt
    return jwt.PyJWKClient(ISSUER + '/.well-known/jwks', cache_keys=True, timeout=5)


def _signing_key(token):
    return _keys().get_signing_key_from_jwt(token).key


def verify_claims(claims, tag):
    ref = claims.get('ref', '')
    if not TAG.fullmatch(tag):
        raise PermissionError('Invalid release tag')
    if not (ref == 'refs/heads/main' and claims.get('event_name') == 'workflow_dispatch'
            or ref == 'refs/tags/' + tag and claims.get('event_name') in {'push', 'workflow_dispatch'}):
        raise PermissionError('Untrusted release reference')
    expected = {'repository':REPOSITORY, 'repository_id':REPOSITORY_ID, 'repository_owner':'sajancodes',
                'repository_owner_id':OWNER_ID, 'repository_visibility':'private',
                'workflow_ref':REPOSITORY + '/.github/workflows/release.yml@' + ref}
    if any(claims.get(key) != value for key, value in expected.items()):
        raise PermissionError('Untrusted release workflow')
    subjects = {f'repo:{REPOSITORY}:ref:{ref}', f'repo:sajancodes@{OWNER_ID}/zaya@{REPOSITORY_ID}:ref:{ref}'}
    if claims.get('sub') not in subjects:
        raise PermissionError('Untrusted release subject')
    if not isinstance(claims.get('iat'), int) or not isinstance(claims.get('exp'), int) or not 0 < claims['exp'] - claims['iat'] <= 900:
        raise PermissionError('Release identity must be short lived')


def authenticate(token, tag):
    import jwt
    try:
        if not token or len(token) > 12000 or jwt.get_unverified_header(token).get('alg') != 'RS256':
            raise PermissionError('Invalid release identity')
        claims = jwt.decode(token, _signing_key(token), algorithms=['RS256'], audience=AUDIENCE,
                            issuer=ISSUER, leeway=10, options={'require':['exp', 'iat', 'nbf', 'iss', 'aud', 'sub']})
        verify_claims(claims, tag)
    except Exception:
        raise PermissionError('A trusted release workflow identity is required') from None
