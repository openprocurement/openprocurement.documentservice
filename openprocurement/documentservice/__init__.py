import gevent.monkey
gevent.monkey.patch_all()
import os
from ConfigParser import ConfigParser
from base64 import b64encode, b64decode
from hashlib import sha512
from libnacl.sign import Signer, Verifier
from logging import getLogger
from pkg_resources import iter_entry_points
from pyramid.authentication import BasicAuthAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.security import Allow
from pytz import timezone

LOGGER = getLogger(__name__)
TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')
USERS = {}


def auth_check(username, password, request):
    if username in USERS and USERS[username]['password'] == sha512(password).hexdigest():
        return ['g:{}'.format(USERS[username]['group'])]


class Root(object):
    def __init__(self, request):
        pass

    __acl__ = [
        (Allow, 'g:uploaders', 'upload'),
        (Allow, 'g:api', 'upload'),
        ]


def read_users(filename):
    config = ConfigParser()
    config.read(filename)
    for i in config.sections():
        USERS.update(dict([
            (
                j,
                {
                    'password': k,
                    'group': i
                }
            )
            for j, k in config.items(i)
        ]))


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    read_users(settings['auth.file'])
    config = Configurator(
        settings=settings,
        authentication_policy=BasicAuthAuthenticationPolicy(auth_check, __name__),
        authorization_policy=ACLAuthorizationPolicy(),
        root_factory=Root,
    )
    config.include('pyramid_exclog')
    config.add_route('register', '/register')
    config.add_route('upload', '/upload')
    config.add_route('upload_file', '/upload/{doc_id}')
    config.add_route('get', '/get/{doc_id}')
    config.scan(ignore='openprocurement.documentservice.tests')

    config.registry.signer = signer = Signer(settings.get('dockey', '').decode('hex'))
    config.registry.dockey = dockey = signer.hex_vk()[:8]
    verifier = Verifier(signer.hex_vk())
    config.registry.dockeyring = dockeyring = {dockey: verifier}
    dockeys = settings.get('dockeys') if 'dockeys' in settings else Signer().hex_vk()
    for key in dockeys.split('\0'):
        dockeyring[key[:8]] = Verifier(key)
    config.registry.keyring = keyring = {dockey: verifier}
    apikeys = settings.get('apikeys') if 'apikeys' in settings else Signer().hex_vk()
    for key in apikeys.split('\0'):
        keyring[key[:8]] = Verifier(key)
    config.registry.apikey = key[:8]

    # search for storage
    storage = settings.get('storage')
    for entry_point in iter_entry_points('openprocurement.documentservice.plugins', storage):
        plugin = entry_point.load()
        plugin(config)

    return config.make_wsgi_app()
