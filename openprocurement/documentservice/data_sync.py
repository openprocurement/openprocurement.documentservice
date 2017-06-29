
import datetime

from uuid import UUID
from logging import getLogger
from celery import Celery
from celery.exceptions import CeleryError
from kombu.exceptions import KombuError
from pymongo import MongoClient
from pymongo.errors import PyMongoError

DOCUMENTS_COLLECTION = 'documents'
TASK_COPY_DOCUMENT = 'task.copy_document'
QUEUE_COPY_DOCUMENT = 'copy_document'
LOGGER = getLogger(__name__)


class DataSyncManager:
    celery = None

    def __init__(self, sync_enabled, mongo_url, current_storage_name, broker_url, timeout):
        self.sync_enabled = sync_enabled
        self.current_storage_name = current_storage_name
        if sync_enabled:
            try:
                client = MongoClient(mongo_url, j=True, serverSelectionTimeoutMS=timeout, connectTimeoutMS=timeout)
                self.database = client.get_default_database()
                self.documents_collection = self.database.get_collection(DOCUMENTS_COLLECTION)
            except PyMongoError as err:
                LOGGER.warning(err, exc_info=True)
            else:
                try:
                    self.celery = Celery('document_service', broker=broker_url)
                    self.celery.conf.task_routes = {
                        TASK_COPY_DOCUMENT: {
                            'queue': QUEUE_COPY_DOCUMENT,
                        }
                    }
                except (CeleryError, KombuError) as err:
                    LOGGER.warning(err, exc_info=True)
        else:
            LOGGER.warning('Sync is disabled')

    def sync_document_register(self, uuid, md5):
        if not self.sync_enabled:
            return
        key = '/'.join([format(i, 'x') for i in UUID(uuid).fields])
        self.__update_mongo_doc(key, {
            'register_hash': md5,
            'registered_on': [self.current_storage_name],
            'create_time': datetime.datetime.now(),
        })
        self.__send_copy_task(key)

    def sync_document_upload(self, uuid, md5, content_type, filename):
        if not self.sync_enabled:
            return
        key = '/'.join([format(i, 'x') for i in UUID(uuid).fields])
        self.__update_mongo_doc(key, {
            'real_hash': md5,
            'uploaded_on': [self.current_storage_name],
            'create_time': datetime.datetime.now(),
            'content_type': content_type,
            'filename': filename,
        })
        self.__send_copy_task(key)

    def __update_mongo_doc(self, key, doc):
        try:
            self.documents_collection.update_one({'key': key}, {'$set': doc}, upsert=True)
        except PyMongoError as err:
            LOGGER.warning(err, exc_info=True)

    def __send_copy_task(self, key):
        if not self.celery:
            return
        try:
            self.celery.send_task(TASK_COPY_DOCUMENT, kwargs={'key': key})
        except (CeleryError, KombuError) as err:
            LOGGER.warning(err, exc_info=True)
