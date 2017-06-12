import bson
import datetime

from pymongo import MongoClient
from uuid import UUID

FILES_COLLECTION = 'files'


def uuidstring_to_mongouuid(uuid):
    return bson.Binary(UUID(uuid).bytes, bson.binary.UUID_SUBTYPE)


class DatabaseWrapper:
    def __init__(self, mongo_url, current_storage_name):
        self.database = MongoClient(mongo_url).get_default_database()
        self.current_storage_name = current_storage_name
        self.files_collection = self.database.get_collection(FILES_COLLECTION)

    def save_file_register(self, uuid, md5):
        doc = {
            'hash': md5,
            'last_modified': datetime.datetime.now(),
            'uploaded': False,
            'registered_on': [self.current_storage_name]
        }
        self.files_collection.update_one({'_id': uuidstring_to_mongouuid(uuid)}, {'$set': doc}, upsert=True)

    def save_file_upload(self, uuid, md5, content_type, filename):
        doc = {
            'hash': md5,
            'last_modified': datetime.datetime.now(),
            'uploaded': True,
            'uploaded_on': [self.current_storage_name],
            'content_type': content_type,
            'filename': filename,
        }
        self.files_collection.update_one({'_id': uuidstring_to_mongouuid(uuid)}, {'$set': doc}, upsert=True)
