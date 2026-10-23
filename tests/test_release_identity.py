"""Real signature verification with fixture keys; no GitHub credentials or network."""
import time

import pytest

jwt = pytest.importorskip('jwt')
from cryptography.hazmat.primitives.asymmetric import rsa
from web import release_identity as identity


def claims():
    now = int(time.time())
    return {'iss':identity.ISSUER, 'aud':identity.AUDIENCE, 'sub':'repo:sajancodes/zaya:ref:refs/heads/main',
            'iat':now, 'nbf':now, 'exp':now + 300, 'repository':'sajancodes/zaya',
            'repository_id':identity.REPOSITORY_ID, 'repository_owner':'sajancodes', 'repository_owner_id':identity.OWNER_ID,
            'repository_visibility':'private', 'ref':'refs/heads/main', 'event_name':'workflow_dispatch',
            'workflow_ref':'sajancodes/zaya/.github/workflows/release.yml@refs/heads/main'}


@pytest.fixture
def signing(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(identity, '_signing_key', lambda token: key.public_key())
    return lambda payload: jwt.encode(payload, key, algorithm='RS256', headers={'kid':'fixture'})


def test_release_workflow_and_immutable_subject_are_accepted(signing):
    payload = claims()
    identity.authenticate(signing(payload), 'v0.5.0')
    payload['sub'] = f'repo:sajancodes@{identity.OWNER_ID}/zaya@{identity.REPOSITORY_ID}:ref:refs/heads/main'
    identity.authenticate(signing(payload), 'v0.5.0')


@pytest.mark.parametrize('field,value', [
    ('repository_id','999'), ('repository_owner_id','999'), ('repository_visibility','public'),
    ('workflow_ref','sajancodes/zaya/.github/workflows/other.yml@refs/heads/main'),
    ('ref','refs/pull/1/merge'), ('event_name','pull_request'), ('aud','another-service'), ('exp',1),
    ('sub','repo:someone/else:ref:refs/heads/main'),
])
def test_other_jobs_forks_audiences_and_expired_tokens_are_denied(signing, field, value):
    payload = claims()
    payload[field] = value
    with pytest.raises(PermissionError, match='trusted release workflow'):
        identity.authenticate(signing(payload), 'v0.5.0')


def test_unsigned_or_tampered_identity_and_wrong_tag_are_denied(signing):
    with pytest.raises(PermissionError):
        identity.authenticate(jwt.encode(claims(), 'fixture-secret-with-at-least-32-characters', algorithm='HS256'), 'v0.5.0')
    token = signing(claims())
    head, body, signature = token.split('.')
    with pytest.raises(PermissionError):
        identity.authenticate(head + '.' + body + '.' + 'a' * len(signature), 'v0.5.0')
    payload = claims()
    payload.update(ref='refs/tags/v0.5.0', event_name='push', sub='repo:sajancodes/zaya:ref:refs/tags/v0.5.0',
                   workflow_ref='sajancodes/zaya/.github/workflows/release.yml@refs/tags/v0.5.0')
    identity.authenticate(signing(payload), 'v0.5.0')
    with pytest.raises(PermissionError):
        identity.authenticate(signing(payload), 'v0.6.0')
