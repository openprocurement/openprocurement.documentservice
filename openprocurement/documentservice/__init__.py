import gevent.monkey
gevent.monkey.patch_all()
import os
from logging import getLogger
from pkg_resources import iter_entry_points
from pyramid.config import Configurator
from pytz import timezone
from pyelliptic import ECC
from base64 import b64encode, b64decode

LOGGER = getLogger(__name__)
TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    config.include('pyramid_exclog')
    config.add_route('register', '/register')
    config.add_route('upload', '/upload/{doc_id}')
    config.add_route('get', '/get/{doc_id}')
    config.scan(ignore='openprocurement.documentservice.tests')

    curve = settings.get('curve')
    privkey = b64decode(settings.get('privkey')) if 'privkey' in settings else None
    pubkey = b64decode(settings.get('pubkey')) if 'pubkey' in settings else None
    apikeys = settings.get('apikeys') if 'apikeys' in settings else b64encode(ECC(curve=curve).get_pubkey())
    keyring = {'doc': ECC(pubkey=pubkey, privkey=privkey, curve=curve)}
    for key in apikeys.split('\0'):
        decoded_key = b64decode(key)
        keyring[decoded_key.encode('hex')[2:10]] = ECC(pubkey=decoded_key, curve=curve)
    config.registry.apikey = decoded_key.encode('hex')[2:10]
    config.registry.keyring = keyring

    # search for storage
    storage = settings.get('storage')
    for entry_point in iter_entry_points('openprocurement.documentservice.plugins', storage):
        plugin = entry_point.load()
        plugin(config)

    return config.make_wsgi_app()
