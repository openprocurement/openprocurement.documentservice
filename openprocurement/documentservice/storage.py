from email.header import decode_header
from hashlib import md5
from openprocurement.documentservice.interfaces import IStorage
from rfc6266 import build_header
from urllib import quote
from uuid import uuid4
from zope.interface import implementer


def get_filename(filename):
    try:
        pairs = decode_header(filename)
    except Exception:
        pairs = None
    if not pairs:
        return filename
    header = pairs[0]
    if header[1]:
        return header[0].decode(header[1])
    else:
        return header[0]


class KeyNotFound(KeyError):
    pass


class MD5Invalid(ValueError):
    pass


class StorageRedirect(Exception):
    def __init__(self, url):
        self.url = url


@implementer(IStorage)
class MemoryStorage:
    storage = {}

    def __init__(self):
        pass

    def register(self, md5hash):
        uuid = uuid4().hex
        self.storage[uuid] = {
            'md5': md5hash,
            'Content': md5hash,
        }
        return uuid

    def upload(self, post_file, uuid=None):
        filename = get_filename(post_file.filename)
        content_type = post_file.type
        in_file = post_file.file
        if uuid is not None and uuid not in self.storage:
            raise KeyNotFound(uuid)
        if uuid is None:
            uuid = uuid4().hex
            key = self.storage[uuid] = {}
        else:
            key = self.storage[uuid]
        content = in_file.read()
        key_md5 = key.get('md5')
        md5hash = md5(content).hexdigest()
        if key_md5 and md5(content).hexdigest() != key_md5:
            raise MD5Invalid(key_md5)
        key['md5'] = md5hash
        key['Content-Type'] = content_type
        key["Content-Disposition"] = build_header(filename, filename_compat=quote(filename.encode('utf-8')))
        key['Content'] = content
        return uuid, md5hash

    def get(self, uuid):
        if uuid not in self.storage:
            raise KeyNotFound(uuid)
        return self.storage[uuid]


def includeme(config):
    config.registry.storage = MemoryStorage()
