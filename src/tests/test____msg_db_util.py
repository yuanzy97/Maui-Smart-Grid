#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel Zhang (張道博)'

import unittest
from msg_db_util import MSGDBUtil
from meco_db_insert import MECODBInserter
from meco_db_connector import MSGDBConnector
from meco_db_delete import MECODBDeleter
from msg_config import MSGConfiger
from msg_logger import MSGLogger


class TestMECODBUtil(unittest.TestCase):
    """
    Unit tests for MECO DB Utils.
    """

    def setUp(self):
        self.i = MECODBInserter()
        self.connector = MSGDBConnector(testing = True)
        self.conn = self.connector.connectDB()
        self.lastSeqVal = None

        # Does this work having the dictCur be in another class?
        self.dictCur = self.connector.dictCur

        self.cursor = self.conn.cursor()
        self.deleter = MECODBDeleter()
        self.tableName = 'MeterData'
        self.columnName = 'meter_data_id'
        self.configer = MSGConfiger()
        self.logger = MSGLogger(__name__, 'debug')
        self.dbUtil = MSGDBUtil()

    def testMECODBUtilCanBeInited(self):
        self.assertIsNotNone(self.dbUtil)

    def testLastSequenceNumberIsCorrect(self):
        """
        Test if last sequence ID value is generated correctly. Do this by
        inserting and deleting a DB record.
        """

        # Insert some values.
        sampleDict = {'MeterName': '100001', 'UtilDeviceID': '100001',
                      'MacID': '00:00:00:00:00:00:00:00'}
        self.i.insertData(self.conn, self.tableName, sampleDict)

        self.lastSeqVal = self.dbUtil.getLastSequenceID(self.conn,
                                                        self.tableName,
                                                        self.columnName)
        print "lastSeqVal = %s" % self.lastSeqVal

        sql = "select * from \"%s\" where %s = %s" % (
            self.tableName, self.columnName, self.lastSeqVal)
        dictCur = self.connector.dictCur
        self.dbUtil.executeSQL(dictCur, sql)
        row = dictCur.fetchone()
        meterDataID = row[self.columnName]
        self.assertEqual(self.lastSeqVal, meterDataID)

    def testGetDBName(self):
        dbName = self.dbUtil.getDBName(self.cursor)[0]
        self.logger.log("DB name is %s" % dbName, 'info')
        self.assertEqual(dbName, "test_meco",
                         "Testing DB name should be set correctly.")


    def testEraseTestingDatabase(self):
        dbName = self.dbUtil.getDBName(self.cursor)[0]
        self.logger.log("DB name is %s" % dbName, 'info')
        self.assertEqual(dbName, "test_meco",
                         "Testing DB name should be set correctly.")
        self.dbUtil.eraseTestMeco()

        # Check all of the tables for the presence of records.
        for table in self.configer.insertTables:
            sql = """select count(*) from "%s";""" % table
            self.dbUtil.executeSQL(self.dictCur, sql)
            row = self.dictCur.fetchone()
            self.assertEqual(row[0], 0,
                             "No records should be present in the %s table."
                             % table)

    def tearDown(self):
        """
        Delete the record that was inserted.
        """
        if self.lastSeqVal != None:
            self.deleter.deleteRecord(self.conn, self.tableName,
                                      self.columnName, self.lastSeqVal)

        self.connector.closeDB(self.conn)


if __name__ == '__main__':
    unittest.main()