from pyramid.view import view_config
from binascii import hexlify
from base64 import b64encode, b64decode
from pyelliptic import ECC
from uuid import uuid4
from time import time
from urllib import quote, unquote
from openprocurement.documentservice.storage import StorageRedirect, MD5Invalid, KeyNotFound

EXPIRES = 300


@view_config(route_name='register', renderer='json', request_method='POST')
def register_view(request):
    if 'filename' not in request.POST or 'md5' not in request.POST:
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "filename or md5", "description": "Not Found"}]
        }
    uuid = request.registry.storage.register(request.POST['filename'], request.POST['md5'])
    url = request.route_url('upload', doc_id=uuid)
    request.response.status = 201
    request.response.headers['Location'] = url
    return url


@view_config(route_name='upload', renderer='json', request_method='POST')
def upload_view(request):
    if 'file' not in request.POST or not hasattr(request.POST['file'], 'filename'):
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "file", "description": "Not Found"}]
        }
    uuid = request.matchdict['doc_id']
    post_file = request.POST['file']
    try:
        request.registry.storage.upload(uuid, post_file)
    except KeyNotFound:
        request.response.status = 404
        return {
            "status": "error",
            "errors": [{ "location": "url", "name": "doc_id", "description": "Not Found"}]
        }
    except MD5Invalid:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "body", "name": "file", "description": "Invalid MD5 checksum"}]
        }
    expires = int(time()) + EXPIRES
    mess = "{}\0{}".format(uuid, expires)
    signature = quote(b64encode(request.registry.keyring['doc'].sign(mess)))
    return request.route_url('get', doc_id=uuid, _query={'Signature': signature, 'Expires': expires, 'KeyID': 'doc'})


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
    keyid = request.GET.get('KeyID', 'doc')
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
    key = request.registry.keyring.get(keyid)
    if 'Signature' not in request.GET:
        request.response.status = 403
        return {
            "status": "error",
            "errors": [{"location": "url", "name": "Signature", "description": "Not Found"}]
        }
    signature = request.GET['Signature']
    if not key.verify(b64decode(unquote(signature)), mess):
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
    except StorageRedirect as e:
        request.response.status = 302
        request.response.headers['Location'] = e.url
        return e.url
    else:
        request.response.content_type = doc['Content-Type']
        request.response.content_disposition = doc['Content-Disposition']
        request.response.body = doc['content']
        return request.response
