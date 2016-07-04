
# -*- coding: utf-8 -*-
import json
import os
from datetime import timedelta, datetime
from uuid import uuid4
from hashlib import md5

import openprocurement.documentservice.tests.base as base_test
from openprocurement.documentservice.tests.base import BaseWebTest
from webtest import TestApp

now = datetime.now()


class DumpsTestAppwebtest(TestApp):
    def do_request(self, req, status=None, expect_errors=None):
        req.headers.environ["HTTP_HOST"] = "docs.api-sandbox.openprocurement.org"
        if hasattr(self, 'file_obj') and not self.file_obj.closed:
            self.file_obj.write(req.as_bytes(True))
            self.file_obj.write("\n\n")
            if req.body:
                try:
                    self.file_obj.write(json.dumps(json.loads(req.body), indent=2, ensure_ascii=False).encode('utf8'))
                except:
                    self.file_obj.write(req.body.encode('utf8'))
                self.file_obj.write("\n\n")
        resp = super(DumpsTestAppwebtest, self).do_request(req, status=status, expect_errors=expect_errors)
        if hasattr(self, 'file_obj') and not self.file_obj.closed:
            headers = [(n.title(), v)
                       for n, v in resp.headerlist
                       if n.lower() != 'content-length']
            headers.sort()
            self.file_obj.write(str('\n%s\n%s\n') % (
                resp.status,
                str('\n').join([str('%s: %s') % (n, v) for n, v in headers]),
            ))

            if resp.testbody:
                try:
                    self.file_obj.write('\n' + json.dumps(json.loads(resp.testbody), indent=2, ensure_ascii=False).encode('utf8'))
                except:
                    pass
            self.file_obj.write("\n\n")
        return resp


class TenderResourceTest(BaseWebTest):

    def setUp(self):
        self.app = DumpsTestAppwebtest(
            "config:tests.ini", relative_to=os.path.dirname(base_test.__file__))
        self.app.authorization = ('Basic', ('broker', 'broker'))

    def test_docs(self):
        with open('docs/source/tutorial/register.http', 'w') as self.app.file_obj:
            md5hash = md5('content').hexdigest()
            response = self.app.post('/register', {'hash': md5hash, 'filename': 'file.txt'})
            self.assertEqual(response.status, '201 Created')
            self.assertEqual(response.content_type, 'application/json')
            self.assertIn('http://docs.api-sandbox.openprocurement.org/upload/', response.json['upload_url'])

        with open('docs/source/tutorial/upload.http', 'w') as self.app.file_obj:
            response = self.app.post(response.json['upload_url'], upload_files=[('file', u'file.txt', 'content')])
            self.assertEqual(response.status, '200 OK')
            self.assertEqual(response.content_type, 'application/json')
            self.assertIn('http://docs.api-sandbox.openprocurement.org/get/', response.json['get_url'])

        with open('docs/source/tutorial/get.http', 'w') as self.app.file_obj:
            response = self.app.get(response.json['get_url'])
            self.assertEqual(response.status, '200 OK')
            self.assertEqual(response.content_type, 'text/plain')
            self.assertEqual(response.body, 'content')

        with open('docs/source/tutorial/upload-file.http', 'w') as self.app.file_obj:
            response = self.app.post('/upload', upload_files=[('file', u'file.txt', 'content')])
            self.assertEqual(response.status, '200 OK')
            self.assertEqual(response.content_type, 'application/json')
            self.assertIn('http://docs.api-sandbox.openprocurement.org/get/', response.json['get_url'])
