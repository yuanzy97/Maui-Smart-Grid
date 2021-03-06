#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel Zhang (張道博)'
__copyright__ = 'Copyright (c) 2013, University of Hawaii Smart Energy Project'
__license__ = 'https://raw.github' \
              '.com/Hawaii-Smart-Energy-Project/Maui-Smart-Grid/master/BSD' \
              '-LICENSE.txt'

import unittest
from msg_db_connector import MSGDBConnector
import msg_db_connector
from msg_configer import MSGConfiger


class TestMSGDBConnect(unittest.TestCase):
    """
    These tests require a database connection to be available.
    """

    def setUp(self):
        self.connector = MSGDBConnector(True)
        self.conn = self.connector.connectDB()
        self.configer = MSGConfiger()

    def test_init(self):
        self.assertTrue(
            isinstance(self.connector, msg_db_connector.MSGDBConnector),
            "self.connection is an instance of MECODBConnector.")

    def test_db_connection(self):
        """
        DB can be connected to.
        """
        self.assertIsNotNone(self.conn, 'DB connection not available.')

        # Get the name of the database.
        self.assertEqual(
            self.configer.configOptionValue('Database', 'testing_db_name'),
            self.connector.dbName, 'Testing DB name is not correct.')

    def tearDown(self):
        self.connector.closeDB(self.conn)


if __name__ == '__main__':
    unittest.main()
