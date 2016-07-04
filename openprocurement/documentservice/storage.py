from email.header import decode_header
from hashlib import md5
from rfc6266 import build_header
from urllib import quote
from uuid import uuid4


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


class HashInvalid(ValueError):
    pass


class NoContent(ValueError):
    pass


class ContentUploaded(ValueError):
    pass


class StorageRedirect(Exception):
    def __init__(self, url):
        self.url = url


class MemoryStorage:
    storage = {}

    def __init__(self):
        pass

    def register(self, md5hash):
        uuid = uuid4().hex
        self.storage[uuid] = {
            'hash': md5hash,
            'Content': '',
        }
        return uuid

    def upload(self, post_file, uuid=None):
        filename = get_filename(post_file.filename)
        content_type = post_file.type
        in_file = post_file.file
        if uuid is not None:
            if uuid not in self.storage:
                raise KeyNotFound(uuid)
            if self.storage[uuid]['Content']:
                raise ContentUploaded(uuid)
            key = self.storage[uuid]
        else:
            uuid = uuid4().hex
            key = self.storage[uuid] = {}
        content = in_file.read()
        key_md5 = key.get('hash')
        md5hash = md5(content).hexdigest()
        if key_md5 and md5(content).hexdigest() != key_md5:
            raise HashInvalid(key_md5)
        key['hash'] = md5hash
        key['Content-Type'] = content_type
        key["Content-Disposition"] = build_header(filename, filename_compat=quote(filename.encode('utf-8')))
        key['Content'] = content
        return uuid, md5hash, content_type, filename

    def get(self, uuid):
        if uuid not in self.storage:
            raise KeyNotFound(uuid)
        if not self.storage[uuid]['Content']:
            raise NoContent(uuid)
        return self.storage[uuid]


def includeme(config):
    config.registry.storage = MemoryStorage()
