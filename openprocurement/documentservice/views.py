from base64 import b64encode, b64decode
from logging import getLogger
from openprocurement.documentservice.storage import StorageRedirect, HashInvalid, KeyNotFound, NoContent, ContentUploaded, StorageUploadError
from openprocurement.documentservice.utils import error_handler, context_unpack
from pyramid.httpexceptions import HTTPNoContent
from pyramid.view import view_config
from time import time
from urllib import quote, unquote

LOGGER = getLogger(__name__)
EXPIRES = 300


@view_config(route_name='status', renderer='string')
def status_view(request):
    return ''


def get_data(request):
    try:
        json = request.json_body
    except ValueError:
        data = request.POST.mixed()
    else:
        data = json.get('data', {})
    return data


@view_config(route_name='register', renderer='json', request_method='POST', permission='upload')
def register_view(request):
    data = get_data(request)
    if not isinstance(data, dict) or 'hash' not in data:
        return error_handler(request, 404, {"location": "body", "name": "hash", "description": "Not Found"})
    md5 = data['hash']
    if not md5.startswith('md5:'):
        return error_handler(request, 422, {"location": "body", "name": "hash", "description": [u'Hash type is not supported.']})
    if len(md5) != 36:
        return error_handler(request, 422, {"location": "body", "name": "hash", "description": [u'Hash value is wrong length.']})
    if set(md5[4:]).difference('0123456789abcdef'):
        return error_handler(request, 422, {"location": "body", "name": "hash", "description": [u'Hash value is not hexadecimal.']})
    try:
        uuid = request.registry.storage.register(md5)
    except StorageUploadError as exc:
        LOGGER.error('Storage error: %s', exc.message, extra=context_unpack(request, {'MESSAGE_ID': 'storage_error'}))
        return error_handler(request, 502, {"description": "Upload failed, please try again later"})
    LOGGER.info('Registered new document upload {}'.format(uuid),
                extra=context_unpack(request, {'MESSAGE_ID': 'registered_upload'}, {'doc_id': uuid, 'doc_hash': md5}))
    signature = quote(b64encode(request.registry.signer.signature(uuid)))
    upload_url = request.route_url('upload_file', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.upload_host or request.domain, _port=request.host_port)
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, md5[4:]))))
    data['url'] = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain, _port=request.host_port)
    request.response.status = 201
    request.response.headers['Location'] = upload_url
    return {'data': data, 'upload_url': upload_url}


@view_config(route_name='upload', renderer='json', request_method='POST', permission='upload')
def upload_view(request):
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        return error_handler(request, 404, {"location": "body", "name": "file", "description": "Not Found"})
    post_file = request.POST['file']
    try:
        uuid, md5, content_type, filename = request.registry.storage.upload(post_file)
    except StorageUploadError as exc:
        LOGGER.error('Storage error: %s', exc.message, extra=context_unpack(request, {'MESSAGE_ID': 'storage_error'}))
        return error_handler(request, 502, {"description": "Upload failed, please try again later"})
    LOGGER.info('Uploaded new document {}'.format(uuid),
                extra=context_unpack(request, {'MESSAGE_ID': 'uploaded_new_document'}, {'doc_id': uuid, 'doc_hash': md5}))
    expires = int(time()) + EXPIRES
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, md5[4:]))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain, _port=request.host_port)
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, expires))))
    get_url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain, _port=request.host_port)
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
    except StorageUploadError as exc:
        LOGGER.error('Storage error: %s', exc.message, extra=context_unpack(request, {'MESSAGE_ID': 'storage_error'}))
        return error_handler(request, 502, {"description": "Upload failed, please try again later"})
    LOGGER.info('Uploaded document {}'.format(uuid),
                extra=context_unpack(request, {'MESSAGE_ID': 'uploaded_document'}, {'doc_hash': md5}))
    expires = int(time()) + EXPIRES
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, md5[4:]))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain, _port=request.host_port)
    signature = quote(b64encode(request.registry.signer.signature("{}\0{}".format(uuid, expires))))
    get_url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': request.registry.dockey}, _host=request.registry.get_host or request.domain, _port=request.host_port)
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
        uuid = '{}/{}'.format(request.GET['Prefix'], uuid)
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
        return HTTPNoContent()
    except StorageRedirect as e:
        request.response.status = 302
        request.response.headers['Location'] = e.url
        return e.url
    else:
        request.response.content_type = doc['Content-Type']
        request.response.content_disposition = doc['Content-Disposition']
        if 'X-Accel-Redirect' in doc:
            request.response.headers['X-Accel-Redirect'] = doc['X-Accel-Redirect']
        else:
            request.response.body = doc['Content']
        return request.response
