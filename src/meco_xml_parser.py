#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel Zhang (張道博)'
__copyright__ = 'Copyright (c) 2013, University of Hawaii Smart Energy Project'
__license__ = 'https://raw.github' \
              '.com/Hawaii-Smart-Energy-Project/Maui-Smart-Grid/master/BSD' \
              '-LICENSE.txt'

import xml.etree.ElementTree as ET
import re
from meco_db_insert import MECODBInserter
from msg_configer import MSGConfiger
from msg_db_util import MSGDBUtil
from meco_mapper import MECOMapper
from msg_db_connector import MSGDBConnector
from meco_fk import MECOFKDeterminer
import sys
from itertools import tee, islice, izip_longest
from meco_dupe_check import MECODupeChecker
from sek.logger import SEKLogger


class MECOXMLParser(object):
    """
    Parses XML for MECO data.
    """

    tableName = ''

    def __init__(self, testing = False):
        """
        Constructor.

        :param testing: (optional) Boolean indicating if Testing Mode is on.
        """

        self.logger = SEKLogger(__name__, 'silent')

        if (testing):
            self.logger.log("Testing Mode is ON.", 'info')

        self.debug = False
        self.configer = MSGConfiger()
        if self.configer.configOptionValue("Debugging", 'debug') == True:
            self.debug = True

        self.util = MSGDBUtil()
        self.mapper = MECOMapper()
        self.connector = MSGDBConnector(testing)
        self.conn = self.connector.connectDB()
        self.filename = None
        self.fileObject = None
        self.processForInsertElementCount = 0
        self.inserter = MECODBInserter()
        self.insertDataIntoDatabase = False

        # Count number of times sections in source data are encountered.
        self.tableNameCount = {'SSNExportDocument': 0, 'MeterData': 0,
                               'RegisterData': 0, 'RegisterRead': 0, 'Tier': 0,
                               'Register': 0, 'IntervalReadData': 0,
                               'Interval': 0, 'Reading': 0, 'IntervalStatus': 0,
                               'ChannelStatus': 0, 'EventData': 0, 'Event': 0}

        # Use this dictionary to track which channels were processed when
        # readings are being processed. this is to prevent duplicate channel
        # data from being inserted.
        self.channelProcessed = {}

        self.initChannelProcessed()

        # Tables to be inserted to.
        self.insertTables = self.configer.insertTables

        self.lastSeqVal = None
        self.fKeyVal = None
        self.lastTable = None
        self.fkDeterminer = MECOFKDeterminer()
        self.dupeChecker = MECODupeChecker()
        self.currentMeterName = None
        self.currentIntervalEndTime = None
        self.currentRegisterReadReadTime = None
        self.dupesExist = False
        self.channelDupeExists = False # For Reading dupes.
        self.numberDupeExists = False # For Register dupes.
        self.eventTimeDupeExists = False # For Event dupes.
        self.commitCount = 0
        self.readingDupeOnInsertCount = 0 # For Reading dupes.
        self.registerDupeOnInsertCount = 0 # For Register dupes.
        self.eventDupeOnInsertCount = 0 # For Event dupes.
        self.dataProcessCount = 0
        self.readingDupeCheckCount = 0 # For Reading dupes.
        self.registerDupeCheckCount = 0 # For Register dupes.
        self.eventDupeCheckCount = 0 # For Event dupes.
        self.insertCount = 0
        self.cumulativeInsertCount = 0
        self.nonProcessForInsertElementCount = 0
        self.readingInsertCount = 0
        self.registerInsertCount = 0
        self.eventInsertCount = 0
        self.totalReadingInsertCount = 0
        self.totalRegisterInsertCount = 0
        self.totalEventInsertCount = 0
        self.totalReadingDupeOnInsertCount = 0
        self.totalRegisterDupeOnInsertCount = 0
        self.totalEventDupeOnInsertCount = 0


    def parseXML(self, fileObject, insert = False, jobID = ''):
        """
        Parse an XML file.

        :param fileObject: a file object referencing an XML file.
        :param insert: (optional) True to insert to the database | False to
        perform no
        inserts.
        :returns: String containing a concise log of parsing.
        """

        print "parseXML:"

        self.commitCount = 0
        self.insertDataIntoDatabase = insert

        parseMsg = "\nParsing XML in %s.\n" % self.filename
        sys.stderr.write(parseMsg)
        parseLog = parseMsg

        tree = ET.parse(fileObject)
        root = tree.getroot()

        parseLog += self.walkTheTreeFromRoot(root, jobID = jobID)

        return parseLog


    def tableNameForAnElement(self, element):
        """
        Get the tablename for an element.

        :param element: Element tree element.
        :returns: table name
        """

        try:
            name = re.search('\{.*\}(.*)', element.tag).group(1)
        except:
            name = None
        return name


    def processDataToBeInserted(self, columnsAndValues, currentTableName,
                                fKeyValue, parseLog, pkeyCol, jobID = ''):
        """
        This is the method that performs insertion of parsed data to the
        database. Duplicate checks are performed on the endpoints of the data
         branches.

        :param columnsAndValues: A dictionary containing columns and their
        values.
        :param currentTableName: The name of the current table.
        :param fKeyValue: The value of the foreign key.
        :param parseLog: String containing a concise log of operations.
        :param pkeyCol: Column name for the primary key.
        :param jobID: Identifier for multiprocessing process.
        :returns: A string containing the parse log.
        """

        self.dataProcessCount += 1

        # Handle a special case for duplicate reading data.
        # Intercept the duplicate reading data before insert.
        if currentTableName == "Reading":
            self.channelDupeExists = self.dupeChecker.readingBranchDupeExists(
                self.conn, self.currentMeterName, self.currentIntervalEndTime,
                columnsAndValues['Channel'])
            self.readingDupeCheckCount += 1

        if currentTableName == "Register":
            self.numberDupeExists = self.dupeChecker.registerBranchDupeExists(
                self.conn, self.currentMeterName,
                self.currentRegisterReadReadTime, columnsAndValues['Number'])
            self.registerDupeCheckCount += 1

        if currentTableName == "Event":
            self.eventTimeDupeExists = self.dupeChecker.eventBranchDupeExists(
                self.conn, self.currentMeterName, columnsAndValues['EventTime'])
            self.eventDupeCheckCount += 1

        # Only perform an insert if there are no duplicate values
        # for the channel.
        if not self.channelDupeExists and not self.numberDupeExists and not \
            self.eventTimeDupeExists:

            # ***********************
            # ***** INSERT DATA *****
            # ***********************
            cur = self.inserter.insertData(self.conn, currentTableName,
                                           columnsAndValues,
                                           fKeyVal = fKeyValue,
                                           withoutCommit = 1)
            # The last 1 indicates don't commit. Commits are handled externally.
            self.insertCount += 1
            self.cumulativeInsertCount += 1

            # Only attempt getting the last sequence value if an insertion
            # took place.
            self.lastSeqVal = self.util.getLastSequenceID(self.conn,
                                                          currentTableName,
                                                          pkeyCol)
            # Store the primary key.
            self.fkDeterminer.pkValforCol[pkeyCol] = self.lastSeqVal

            if currentTableName == "Reading":
                self.readingInsertCount += 1
                self.totalReadingInsertCount += 1
            elif currentTableName == "Register":
                self.registerInsertCount += 1
                self.totalRegisterInsertCount += 1
            elif currentTableName == "Event":
                self.eventInsertCount += 1
                self.totalEventInsertCount += 1

        else: # Don't insert into Reading or Register table if a dupe exists.

            if (self.channelDupeExists):
                self.readingDupeOnInsertCount += 1
                self.totalReadingDupeOnInsertCount += 1
                if self.readingDupeOnInsertCount > 0 and self\
                    .readingDupeOnInsertCount < 2:
                    parseLog += self.logger.logAndWrite(
                        "%s:{rd-dupe==>}" % jobID)

                # Also, verify the data is equivalent to the existing record.
                matchingValues = self.dupeChecker.readingValuesAreInTheDatabase(
                    self.conn, columnsAndValues)
                assert matchingValues == True, "Duplicate check found " \
                                               "non-matching values for meter" \
                                               " %s," \
                                               " endtime %s, channel %s (%s, " \
                                               "%s)." % (
                                                   self.currentMeterName,
                                                   self.currentIntervalEndTime,
                                                   columnsAndValues['Channel'],
                                                   columnsAndValues['RawValue'],
                                                   columnsAndValues['Value'])

                self.channelDupeExists = False

            elif (self.numberDupeExists):
                self.registerDupeOnInsertCount += 1
                self.totalRegisterDupeOnInsertCount += 1
                if self.registerDupeOnInsertCount > 0 and self\
                    .registerDupeOnInsertCount < 2:
                    parseLog += self.logger.logAndWrite(
                        "%s:{re-dupe==>}" % jobID)

                self.numberDupeExists = False

            elif (self.eventTimeDupeExists):
                self.eventDupeOnInsertCount += 1
                self.totalEventDupeOnInsertCount += 1
                if self.eventDupeOnInsertCount > 0 and self\
                    .eventDupeOnInsertCount < 2:
                    parseLog += self.logger.logAndWrite(
                        "%s:{ev-dupe==>}" % jobID)

                self.eventTimeDupeExists = False

            else:
                assert True == False, "Duplicate condition does not exist."

            self.logger.log('Record not inserted for %s.' % columnsAndValues,
                            'silent')

        return parseLog

    def generateConciseLogEntries(self, jobID = '', reportType = None):
        """
        Create log entries in the concise log.

        :param jobID: Identifier used to distinguish multiprocessing jobs.
        :returns: A concatenated string of log entries.
        """

        # @todo Change report type to enum type.

        log = ''
        if reportType == 'FINAL':
            self.logger.log('Final report', 'info')

            if self.readingDupeOnInsertCount > 0 or self\
                .registerDupeOnInsertCount > 0 or self.eventDupeOnInsertCount\
                    > 0:
                log = self.logger.logAndWrite("%s:{%srd,%sre,%sev}" % (
                    jobID, self.totalReadingDupeOnInsertCount,
                    self.totalRegisterDupeOnInsertCount,
                    self.totalEventDupeOnInsertCount))
            else:
                log = ''
            log += self.logger.logAndWrite("(%s)" % self.commitCount)
            log += self.logger.logAndWrite(
                "[%s]" % self.processForInsertElementCount)
            log += self.logger.logAndWrite("<%srd,%sre,%sev,%s>" % (
                self.totalReadingInsertCount, self.totalRegisterInsertCount,
                self.totalEventInsertCount, self.cumulativeInsertCount))

        elif reportType == 'INTERMEDIARY':

            if self.readingDupeOnInsertCount > 0 or self\
                .registerDupeOnInsertCount > 0 or self.eventDupeOnInsertCount\
                    > 0:
                log = self.logger.logAndWrite("%s:{%srd,%sre,%sev}" % (
                    jobID, self.readingDupeOnInsertCount,
                    self.registerDupeOnInsertCount,
                    self.eventDupeOnInsertCount))
            else:
                log = ''
            log += self.logger.logAndWrite("(%s)" % self.commitCount)
            log += self.logger.logAndWrite(
                "[%s]" % self.processForInsertElementCount)
            log += self.logger.logAndWrite("<%srd,%sre,%sev,%s,%s>" % (
                self.readingInsertCount, self.registerInsertCount,
                self.eventInsertCount, self.insertCount,
                self.cumulativeInsertCount))
        return log

    def resetGroupCounters(self):
        """
        Reset counters that are keeping track of groups.
        """

        self.readingDupeOnInsertCount = 0
        self.insertCount = 0
        self.readingInsertCount = 0
        self.registerDupeOnInsertCount = 0
        self.registerInsertCount = 0
        self.eventInsertCount = 0
        self.eventDupeOnInsertCount = 0

    def performTableBasedOperations(self, columnsAndValues, currentTableName,
                                    element):
        """
        Perform operations that are based on the current table.

        :param columnsAndValues
        :param currentTableName
        :param element
        """

        if currentTableName == "MeterData":
            self.currentMeterName = columnsAndValues['MeterName']

        elif currentTableName == "Interval":
            self.currentIntervalEndTime = columnsAndValues['EndTime']

        elif currentTableName == "RegisterRead":
            self.currentRegisterReadReadTime = columnsAndValues['ReadTime']

        elif currentTableName == "Event":
            columnsAndValues['Event_Content'] = element.text


    def walkTheTreeFromRoot(self, root, jobID = ''):
        """
        Walk an XML tree from its root node.

        :param root: The root node of an XML tree.
        :param jobID: Identifier used to distinguish multiprocessing jobs.
        :returns: String containing a concise log of parsing activity.
        """

        parseLog = ''
        walker = root.iter()

        for element, nextElement in self.getNext(walker):
            # Process every element in the tree while reading ahead to get
            # the next element.

            currentTableName = self.tableNameForAnElement(element)
            nextTableName = self.tableNameForAnElement(nextElement)
            assert currentTableName is not None, "Current table does not exist."

            # Maintain a count of tables encountered.
            self.tableNameCount[currentTableName] += 1

            columnsAndValues = {}
            it = iter(sorted(element.attrib.iteritems()))

            for item in list(it):
                # Create a dictionary of column names and values.
                columnsAndValues[item[0]] = item[1]

            if currentTableName in self.insertTables:
                # Check if the current table is one of the tables to have data
                # inserted.

                self.processForInsertElementCount += 1

                if self.debug:
                    self.logger.log("Processing table %s, next is %s." % (
                        currentTableName, nextTableName), 'debug')

                # Get the column name for the primary key.
                pkeyCol = self.mapper.dbColumnsForTable(currentTableName)[
                    '_pkey']

                fkeyCol = None
                fKeyValue = None

                try:
                    # Get the column name for the foreign key.
                    fkeyCol = self.mapper.dbColumnsForTable(currentTableName)[
                        '_fkey']
                except:
                    pass

                if self.debug:
                    self.logger.log("foreign key col (fkey) = %s" % fkeyCol,
                                    'debug')
                    self.logger.log("primary key col (pkey) = %s" % pkeyCol,
                                    'debug')
                    self.logger.log(columnsAndValues, 'debug')

                if fkeyCol is not None:
                    # Get the foreign key value.
                    fKeyValue = self.fkDeterminer.pkValforCol[fkeyCol]

                if self.debug:
                    self.logger.log("fKeyValue = %s" % fKeyValue, 'debug')

                self.performTableBasedOperations(columnsAndValues,
                                                 currentTableName, element)

                if self.insertDataIntoDatabase:
                    # Data is intended to be inserted into the database.
                    parseLog = self.processDataToBeInserted(columnsAndValues,
                                                            currentTableName,
                                                            fKeyValue, parseLog,
                                                            pkeyCol,
                                                            jobID = jobID)

                if self.debug:
                    self.logger.log("lastSeqVal = ", self.lastSeqVal)

                if self.lastReading(currentTableName, nextTableName):
                    # The last reading set has been reached.

                    if self.debug:
                        self.logger.log("----- last reading found -----",
                                        'debug')

                    parseLog += self.generateConciseLogEntries(jobID = jobID,
                                                               reportType =
                                                               'INTERMEDIARY')
                    self.resetGroupCounters()

                    parseLog += self.logger.logAndWrite("*")
                    self.commitCount += 1
                    self.conn.commit()

                if self.lastRegister(currentTableName, nextTableName):
                    # The last register set has been reached.

                    if self.debug:
                        self.logger.log("----- last register found -----",
                                        'debug')


        # Initial commit.
        if self.commitCount == 0:
            parseLog += self.generateConciseLogEntries(jobID = jobID,
                                                       reportType =
                                                       'INTERMEDIARY')
        self.resetGroupCounters()

        # Final commit.
        parseLog += self.logger.logAndWrite("---")
        parseLog += self.generateConciseLogEntries(jobID = jobID,
                                                   reportType = 'FINAL')
        self.resetGroupCounters()

        parseLog += self.logger.logAndWrite("*")
        self.commitCount += 1
        self.conn.commit()
        sys.stderr.write("\n")

        self.logger.log("Data process count = %s." % self.dataProcessCount,
                        'info')
        self.logger.log(
            "Reading dupe check count = %s." % self.readingDupeCheckCount,
            'info')
        return parseLog


    def lastReading(self, currentTable, nextTable):
        """
        Determine if the last reading is being visited.

        :param currentTable: current table being processsed.
        :param nextTable: next table to be processed.
        :returns: True if last object in Reading table was read,
        otherwise return False.
        """

        if currentTable == "Reading" and (
                    nextTable == "MeterData" or nextTable == None):
            return True
        return False


    def lastRegister(self, currentTable, nextTable):
        """
        Determine if the last register is being visited.

        :param currentTable: current table being processsed.
        :param nextTable: next table to be processed.
        :returns: True if last object in Register table was read,
        otherwise return False.
        """

        if currentTable == "Register" and (
                    nextTable == "MeterData" or nextTable == None):
            return True
        return False


    def getNext(self, somethingIterable, window = 1):
        """
        Return the current item and next item in an iterable data structure.

        :param somethingIterable: Something that has an iterator.
        :param window: How far to look ahead in the collection.
        :returns: The current iterable value and the next iterable value.
        """

        items, nexts = tee(somethingIterable, 2)
        nexts = islice(nexts, window, None)
        return izip_longest(items, nexts)


    def initChannelProcessed(self):
        """
        Initialize the dictionary for channel processing.
        """

        self.channelProcessed = {'1': False, '2': False, '3': False, '4': False}


    def getLastElement(self, rows):
        """
        Get the last element in a collection.

        Example:
            rows = (element1, element2, element3)
            getLastElement(rows) # return element3

        :param rows: Result rows from a query.
        :returns: The last element in the collection.
        """

        for i, var in enumerate(rows):
            if i == len(rows) - 1:
                return var
