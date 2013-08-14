#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel Zhang (張道博)'
__copyright__ = 'Copyright (c) 2013, University of Hawaii Smart Energy Project'
__license__ = 'https://raw.github' \
              '.com/Hawaii-Smart-Energy-Project/Maui-Smart-Grid/master/BSD' \
              '-LICENSE.txt'

from msg_logger import MSGLogger
from msg_time_util import MSGTimeUtil
import subprocess
from msg_configer import MSGConfiger


class MSGDBExporter(object):
    """
    Export MSG DBs as SQL scripts.
    """

    def __init__(self):
        """
        Constructor.
        """
        self.logger = MSGLogger(__name__)
        self.timeUtil = MSGTimeUtil()
        self.configer = MSGConfiger()

    def exportDB(self, databases):
        """
        Export a DB to local storage.

        Uses

        pg_dump -s -h ${HOST} ${DB_NAME} > ${DUMP_TIMESTAMP}_{DB_NAME}.sql

        :param: databases: List of database names.
        """

        host = self.configer.configOptionValue('Database', 'db_host')

        for db in databases:
            conciseNow = self.timeUtil.conciseNow()
            dumpName = "%s_%s" % (conciseNow, db)
            command = """pg_dump -h %s %s > %s/%s.sql""" % (host, db,
                                                            self.configer
                                                            .configOptionValue(
                                                                'Export',
                                                                'db_export_path'),
                                                            dumpName)
            try:
                subprocess.check_call(command, shell = True)
            except subprocess.CalledProcessError, e:
                self.logger.log("An exception occurred: %s", e)


if __name__ == '__main__':
    exporter = MSGDBExporter()
    exporter.exportDB(
        [exporter.configer.configOptionValue('Export', 'dbs_to_export')])

