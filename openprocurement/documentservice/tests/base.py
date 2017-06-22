# -*- coding: utf-8 -*-
import unittest
import mock
import webtest
import os


class BaseWebTest(unittest.TestCase):

    """Base Web Test to test openprocurement.api.

    It setups the database before each test and delete it after.
    """
    def setUp(self):
        with mock.patch('openprocurement.documentservice.DataSyncManager'):
            self.app = webtest.TestApp(
                "config:tests.ini", relative_to=os.path.dirname(__file__))
            self.app.authorization = ('Basic', ('broker', 'broker'))

    def tearDown(self):
        pass
