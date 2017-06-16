import bson
import datetime

from pymongo import MongoClient
from uuid import UUID

DOCUMENTS_COLLECTION = 'documents'


def uuidstring_to_mongouuid(uuid):
    return bson.Binary(UUID(uuid).bytes, bson.binary.UUID_SUBTYPE)


class DatabaseWrapper:
    def __init__(self, mongo_url, current_storage_name):
        self.database = MongoClient(mongo_url).get_default_database()
        self.current_storage_name = current_storage_name
        self.documents_collection = self.database.get_collection(DOCUMENTS_COLLECTION)

    def save_document_register(self, uuid, md5):
        doc = {
            'register_hash': md5,
            'registered_on': [self.current_storage_name],
            'create_time': datetime.datetime.now(),
        }
        self.documents_collection.update_one({'_id': uuidstring_to_mongouuid(uuid)}, {'$set': doc}, upsert=True)

    def save_document_upload(self, uuid, md5, content_type, filename):
        doc = {
            'real_hash': md5,
            'uploaded_on': [self.current_storage_name],
            'create_time': datetime.datetime.now(),
            'content_type': content_type,
            'filename': filename,
        }
        self.documents_collection.update_one({'_id': uuidstring_to_mongouuid(uuid)}, {'$set': doc}, upsert=True)
