import gevent.monkey
gevent.monkey.patch_all()
import os
from logging import getLogger
from pkg_resources import iter_entry_points
from pyramid.config import Configurator
from pyramid.authentication import BasicAuthAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pytz import timezone
from pyelliptic import ECC
from base64 import b64encode, b64decode
from ConfigParser import ConfigParser
from hashlib import sha512


LOGGER = getLogger(__name__)
TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')
USERS = {}


def auth_check(username, password, request):
    if username in USERS and USERS[username]['password'] == sha512(password).hexdigest():
        return ['g:{}'.format(USERS[username]['group'])]


from pyramid.security import Allow
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

    curve = settings.get('curve', 'secp384r1')
    privkey = b64decode(settings.get('privkey')) if 'privkey' in settings else None
    pubkey = b64decode(settings.get('pubkey')) if 'pubkey' in settings else None
    dockeys = settings.get('dockeys') if 'dockeys' in settings else b64encode(ECC(curve=curve).get_pubkey())
    dockey = ECC(pubkey=pubkey, privkey=privkey, curve=curve)
    config.registry.dockey = dockey.get_pubkey().encode('hex')[2:10]
    config.registry.dockeyring = dockeyring = {config.registry.dockey: dockey}
    for key in dockeys.split('\0'):
        decoded_key = b64decode(key)
        dockeyring[decoded_key.encode('hex')[2:10]] = ECC(pubkey=decoded_key, curve=curve)
    apikeys = settings.get('apikeys') if 'apikeys' in settings else b64encode(ECC(curve=curve).get_pubkey())
    config.registry.dockey = dockey.get_pubkey().encode('hex')[2:10]
    config.registry.keyring = keyring = {config.registry.dockey: dockey}
    for key in apikeys.split('\0'):
        decoded_key = b64decode(key)
        keyring[decoded_key.encode('hex')[2:10]] = ECC(pubkey=decoded_key, curve=curve)
    config.registry.apikey = decoded_key.encode('hex')[2:10]

    # search for storage
    storage = settings.get('storage')
    for entry_point in iter_entry_points('openprocurement.documentservice.plugins', storage):
        plugin = entry_point.load()
        plugin(config)

    return config.make_wsgi_app()
