# -*- coding: utf-8 -*-

import unittest
from hashlib import md5
from openprocurement.documentservice.tests.base import BaseWebTest


class SimpleTest(BaseWebTest):

    def test_root(self):
        response = self.app.get('/', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'text/plain')

    def test_register_get(self):
        response = self.app.get('/register', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'text/plain')

    def test_upload_get(self):
        response = self.app.get('/upload', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'text/plain')

    def test_upload_file_get(self):
        response = self.app.get('/upload/uuid', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'text/plain')

    def test_register_invalid(self):
        url = '/register'
        response = self.app.post(url, 'data', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'body', u'name': u'md5'}
        ])

        response = self.app.post(url, {'not_md5': 'hash'}, status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'body', u'name': u'md5'}
        ])

    def test_register_post(self):
        response = self.app.post('/register', {'md5': 'hash', 'filename': 'file.txt'})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/upload/', response.json['upload_url'])

    def test_upload_invalid(self):
        url = '/upload'
        response = self.app.post(url, 'data', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'body', u'name': u'file'}
        ])

    def test_upload_post(self):
        response = self.app.post('/upload', upload_files=[('file', u'file.txt', 'content')])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/get/', response.json['get_url'])

    def test_upload_file_invalid(self):
        url = '/upload/uuid'
        response = self.app.post(url, 'data', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'body', u'name': u'file'}
        ])

        response = self.app.post(url, upload_files=[('file', u'file.doc', 'content')], status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'url', u'name': u'doc_id'}
        ])

    def test_upload_file_md5(self):
        response = self.app.post('/register', {'md5': 'hash', 'filename': 'file.txt'})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/upload/', response.json['upload_url'])

        response = self.app.post(response.json['upload_url'], upload_files=[('file', u'file.doc', 'content')], status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Invalid MD5 checksum', u'name': u'file', u'location': u'body'}
        ])

    def test_upload_file_post(self):
        content = 'content'
        md5hash = md5(content).hexdigest()
        response = self.app.post('/register', {'md5': md5hash, 'filename': 'file.txt'})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/upload/', response.json['upload_url'])

        response = self.app.post(response.json['upload_url'], upload_files=[('file', u'file.txt', 'content')])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/get/', response.json['get_url'])

    def test_get_invalid(self):
        response = self.app.get('/get/uuid', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Key Id does permit to get private document', u'name': u'KeyID', u'location': u'url'}
        ])

        response = self.app.get('/get/uuid?Expires=1', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Request has expired', u'name': u'Expires', u'location': u'url'}
        ])

        response = self.app.get('/get/uuid?Expires=2000000000', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'name': u'Signature', u'location': u'url'}
        ])

        response = self.app.get('/get/uuid?Expires=2000000000&Signature=', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Signature does not match', u'name': u'Signature', u'location': u'url'}
        ])

        response = self.app.get('/get/uuid?Expires=2000000000&Signature=&KeyID=test', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Key Id does not exist', u'name': u'KeyID', u'location': u'url'}
        ])

    def test_get_md5(self):
        md5hash = md5('content').hexdigest()
        response = self.app.post('/register', {'md5': md5hash, 'filename': 'file.txt'})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/upload/', response.json['upload_url'])

        response = self.app.post(response.json['upload_url'], upload_files=[('file', u'file.txt', 'content')])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/get/', response.json['get_url'])

        response = self.app.get(response.json['get_url'])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.body, 'content')

    def test_get(self):
        response = self.app.post('/upload', upload_files=[('file', u'file.txt', 'content')])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertIn('http://localhost/get/', response.json['get_url'])

        response = self.app.get(response.json['get_url'])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.body, 'content')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SimpleTest))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
