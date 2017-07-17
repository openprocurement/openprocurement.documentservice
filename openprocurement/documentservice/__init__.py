import gevent.monkey
gevent.monkey.patch_all()
from libnacl.sign import Signer, Verifier
from openprocurement.documentservice.utils import auth_check, Root, add_logging_context, read_users, request_params, new_request_subscriber
from pkg_resources import iter_entry_points
from pyramid.authentication import BasicAuthAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.events import ContextFound, NewRequest


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
    config.add_request_method(request_params, 'params', reify=True)
    config.add_subscriber(new_request_subscriber, NewRequest)
    config.add_subscriber(add_logging_context, ContextFound)
    config.include('pyramid_exclog')
    config.add_route('status', '/')
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

    config.registry.upload_host = settings.get('upload_host')
    config.registry.get_host = settings.get('get_host')

    # search for storage
    storage = settings.get('storage')
    for entry_point in iter_entry_points('openprocurement.documentservice.plugins', storage):
        plugin = entry_point.load()
        config.registry.storage = plugin(config)

    return config.make_wsgi_app()
