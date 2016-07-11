from pyramid.view import view_config
from base64 import b64encode, b64decode
from time import time
from urllib import quote, unquote
from openprocurement.documentservice.storage import StorageRedirect, HashInvalid, KeyNotFound, NoContent, ContentUploaded
from openprocurement.documentservice.utils import error_handler, context_unpack
from logging import getLogger

LOGGER = getLogger(__name__)
EXPIRES = 300


@view_config(route_name='status', renderer='json')
def status_view(request):
    request.response.status = 204
    request.response.content_type = ''


@view_config(route_name='register', renderer='json', request_method='POST', permission='upload')
def register_view(request):
    if 'hash' not in request.POST:
        return error_handler(request, 404, {"location": "body", "name": "hash", "description": "Not Found"})
    md5 = request.POST['hash']
    uuid = request.registry.storage.register(md5)
    LOGGER.info('Registered new document upload {}'.format(uuid),
                extra=context_unpack(request, {'MESSAGE_ID': 'registered_upload'}, {'doc_id': uuid, 'doc_hash': md5}))
    signature = quote(b64encode(request.registry.signer.signature(uuid)))
    upload_url = request.route_url('upload_file', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.upload_host or request.domain)
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, md5))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain)
    request.response.status = 201
    request.response.headers['Location'] = upload_url
    return {'data': {'url': url, 'hash': md5}, 'upload_url': upload_url}


@view_config(route_name='upload', renderer='json', request_method='POST', permission='upload')
def upload_view(request):
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        return error_handler(request, 404, {"location": "body", "name": "file", "description": "Not Found"})
    post_file = request.POST['file']
    uuid, md5, content_type, filename = request.registry.storage.upload(post_file)
    LOGGER.info('Uploaded new document {}'.format(uuid),
                extra=context_unpack(request, {'MESSAGE_ID': 'uploaded_new_document'}, {'doc_id': uuid, 'doc_hash': md5}))
    expires = int(time()) + EXPIRES
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, md5))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain)
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, expires))))
    get_url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain)
    request.response.headers['Location'] = get_url
    return {'data': {'url': url, 'hash': md5, 'format': content_type, 'title': filename}, 'get_url': get_url}


@view_config(route_name='upload_file', renderer='json', request_method='POST', permission='upload')
def upload_file_view(request):
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        return error_handler(request, 404, {"location": "body", "name": "file", "description": "Not Found"})
    uuid = request.matchdict['doc_id']
    keyid = request.GET.get('KeyID', request.registry.dockey)
    if keyid not in request.registry.dockeyring:
        return error_handler(request, 403, {"location": "url", "name": "KeyID", "description": "Key Id does not exist"})
    key = request.registry.dockeyring.get(keyid)
    if 'Signature' not in request.GET:
        return error_handler(request, 403, {"location": "url", "name": "Signature", "description": "Not Found"})
    signature = request.GET['Signature']
    try:
        signature = b64decode(unquote(signature))
    except TypeError:
        return error_handler(request, 403, {"location": "url", "name": "Signature", "description": "Signature invalid"})
    try:
        if uuid != key.verify(signature + uuid.encode("utf-8")):
            raise ValueError
    except ValueError:
        return error_handler(request, 403, {"location": "url", "name": "Signature", "description": "Signature does not match"})
    post_file = request.POST['file']
    try:
        uuid, md5, content_type, filename = request.registry.storage.upload(post_file, uuid)
    except KeyNotFound:
        return error_handler(request, 404, {"location": "url", "name": "doc_id", "description": "Not Found"})
    except ContentUploaded:
        return error_handler(request, 403, {"location": "url", "name": "doc_id", "description": "Content already uploaded"})
    except HashInvalid:
        return error_handler(request, 403, {"location": "body", "name": "file", "description": "Invalid checksum"})
    LOGGER.info('Uploaded document {}'.format(uuid),
                extra=context_unpack(request, {'MESSAGE_ID': 'uploaded_document'}, {'doc_hash': md5}))
    expires = int(time()) + EXPIRES
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, md5))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain)
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, expires))))
    get_url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain)
    return {'data': {'url': url, 'hash': md5, 'format': content_type, 'title': filename}, 'get_url': get_url}


@view_config(route_name='get', renderer='json', request_method='GET')
def get_view(request):
    uuid = request.matchdict['doc_id']
    now = int(time())
    expires = request.GET.get('Expires')
    if expires and expires.isdigit() and int(expires) < now:
        return error_handler(request, 403, {"location": "url", "name": "Expires", "description": "Request has expired"})
    keyid = request.GET.get('KeyID', request.registry.dockey)
    if keyid not in (request.registry.apikey, request.registry.dockey) and not expires:
        return error_handler(request, 403, {"location": "url", "name": "KeyID", "description": "Key Id does permit to get private document"})
    if keyid not in request.registry.keyring:
        return error_handler(request, 403, {"location": "url", "name": "KeyID", "description": "Key Id does not exist"})
    mess = "{}\0{}".format(uuid, expires) if expires else uuid
    if request.GET.get('Prefix'):
        mess = '{}/{}'.format(request.GET['Prefix'], mess)
        keyid = '{}/{}'.format(request.GET['Prefix'], uuid)
    key = request.registry.keyring.get(keyid)
    if 'Signature' not in request.GET:
        return error_handler(request, 403, {"location": "url", "name": "Signature", "description": "Not Found"})
    signature = request.GET['Signature']
    try:
        signature = b64decode(unquote(signature))
    except TypeError:
        return error_handler(request, 403, {"location": "url", "name": "Signature", "description": "Signature invalid"})
    try:
        if mess != key.verify(signature + mess.encode("utf-8")):
            raise ValueError
    except ValueError:
        return error_handler(request, 403, {"location": "url", "name": "Signature", "description": "Signature does not match"})
    try:
        doc = request.registry.storage.get(uuid)
    except KeyNotFound:
        return error_handler(request, 404, {"location": "url", "name": "doc_id", "description": "Not Found"})
    except NoContent:
        request.response.status = 204
        request.response.content_type = ''
        return
    except StorageRedirect as e:
        request.response.status = 302
        request.response.headers['Location'] = e.url
        return e.url
    else:
        request.response.content_type = doc['Content-Type']
        request.response.content_disposition = doc['Content-Disposition']
        request.response.body = doc['Content']
        return request.response
