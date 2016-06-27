from pyramid.view import view_config
from base64 import b64encode, b64decode
from time import time
from urllib import quote, unquote
from openprocurement.documentservice.storage import StorageRedirect, MD5Invalid, KeyNotFound, NoContent

EXPIRES = 300


@view_config(route_name='register', renderer='json', request_method='POST', permission='upload')
def register_view(request):
    if 'md5' not in request.POST:
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "md5", "description": "Not Found"}]
        }
    md5 = request.POST['md5']
    uuid = request.registry.storage.register(md5)
    upload_url = request.route_url('upload_file', doc_id=uuid)
    signature = quote(b64encode(request.registry.keyring[request.registry.dockey].sign("{}\0{}".format(uuid, md5))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey})
    request.response.status = 201
    request.response.headers['Location'] = upload_url
    return {'data': {'url': url, 'md5': md5}, 'upload_url': upload_url}


@view_config(route_name='upload', renderer='json', request_method='POST', permission='upload')
def upload_view(request):
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "file", "description": "Not Found"}]
        }
    post_file = request.POST['file']
    uuid, md5, content_type, filename = request.registry.storage.upload(post_file)
    expires = int(time()) + EXPIRES
    mess = "{}\0{}".format(uuid, expires)
    signature = quote(b64encode(request.registry.keyring[request.registry.dockey].sign("{}\0{}".format(uuid, md5))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey})
    signature = quote(b64encode(request.registry.keyring[request.registry.dockey].sign(mess)))
    get_url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': request.registry.dockey})
    request.response.headers['Location'] = get_url
    return {'data': {'url': url, 'md5': md5, 'format': content_type, 'title': filename}, 'get_url': get_url}


@view_config(route_name='upload_file', renderer='json', request_method='POST', permission='upload')
def upload_file_view(request):
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "file", "description": "Not Found"}]
        }
    uuid = request.matchdict['doc_id']
    post_file = request.POST['file']
    try:
        uuid, md5, content_type, filename = request.registry.storage.upload(post_file, uuid)
    except KeyNotFound:
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "doc_id", "description": "Not Found"}]
        }
    except MD5Invalid:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "file", "description": "Invalid MD5 checksum"}]
        }
    expires = int(time()) + EXPIRES
    mess = "{}\0{}".format(uuid, expires)
    signature = quote(b64encode(request.registry.keyring[request.registry.dockey].sign("{}\0{}".format(uuid, md5))))
    url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'KeyID': request.registry.dockey})
    signature = quote(b64encode(request.registry.keyring[request.registry.dockey].sign(mess)))
    get_url = request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': request.registry.dockey})
    return {'data': {'url': url, 'md5': md5, 'format': content_type, 'title': filename}, 'get_url': get_url}


@view_config(route_name='get', renderer='json', request_method='GET')
def get_view(request):
    uuid = request.matchdict['doc_id']
    now = int(time())
    expires = request.GET.get('Expires')
    if expires and expires.isdigit() and int(expires) < now:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "Expires", "description": "Request has expired"}]
        }
    keyid = request.GET.get('KeyID', request.registry.dockey)
    if keyid != request.registry.apikey and not expires:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "KeyID", "description": "Key Id does permit to get private document"}]
        }
    if keyid not in request.registry.keyring:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "KeyID", "description": "Key Id does not exist"}]
        }
    mess = "{}\0{}".format(uuid, expires) if expires else uuid
    if request.GET.get('Prefix'):
        mess = '{}/{}'.format(request.GET['Prefix'], mess)
        keyid = '{}/{}'.format(request.GET['Prefix'], uuid)
    key = request.registry.keyring.get(keyid)
    if 'Signature' not in request.GET:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "Signature", "description": "Not Found"}]
        }
    signature = request.GET['Signature']
    try:
        signature = b64decode(unquote(signature))
    except TypeError:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "Signature", "description": "Signature invalid"}]
        }
    if not key.verify(signature, mess):
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "Signature", "description": "Signature does not match"}]
        }
    try:
        doc = request.registry.storage.get(uuid)
    except KeyNotFound:
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "doc_id", "description": "Not Found"}]
        }
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
