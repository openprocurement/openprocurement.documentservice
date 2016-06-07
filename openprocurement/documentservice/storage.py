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

    def register(self, filename, md5hash):
        uuid = uuid4().hex
        self.storage[uuid] = {
            'md5': md5hash,
            "Content-Disposition": build_header(filename, filename_compat=quote(filename.encode('utf-8'))),
            'content': md5hash,
        }
        return uuid

    def upload(self, uuid, post_file):
        filename = get_filename(post_file.filename)
        content_type = post_file.type
        in_file = post_file.file
        if uuid not in self.storage:
            raise KeyNotFound(uuid)
        key = self.storage[uuid]
        md5hash = key.get('md5')
        content = in_file.read()
        if md5(content).hexdigest() != md5hash:
            raise MD5Invalid(md5hash)
        key['Content-Type'] = content_type
        key["Content-Disposition"] = build_header(filename, filename_compat=quote(filename.encode('utf-8')))
        key['content'] = content

    def get(self, uuid):
        if uuid not in self.storage:
            raise KeyNotFound(uuid)
        return self.storage[uuid]


def includeme(config):
    config.registry.storage = MemoryStorage()
