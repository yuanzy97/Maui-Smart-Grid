#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel Zhang (張道博)'
__copyright__ = 'Copyright (c) 2013, University of Hawaii Smart Energy Project'
__license__ = 'https://raw.github' \
              '.com/Hawaii-Smart-Energy-Project/Maui-Smart-Grid/master/BSD' \
              '-LICENSE.txt'

from msg_db_connector import MSGDBConnector
from msg_db_util import MSGDBUtil
import csv


def replaceNull(s):
    if s == 'NULL':
        return 'NULL'
    else:
        return s


connector = MSGDBConnector()
conn = connector.connectDB()
dbUtil = MSGDBUtil()
cursor = conn.cursor()

files = ['avg-irradiance-15-min-2012-first-half.csv',
         'avg-irradiance-15-min-2012-second-half.csv',
         'avg-irradiance-15-min-2013-first-half.csv',
         'avg-irradiance-15-min-2013-second-half.csv']
table = 'AverageFifteenMinIrradianceData'
cols = ['sensor_id', 'timestamp', 'irradiance_w_per_m2']

cnt = 0

for file in files:

    with open(file, 'rb') as csvfile:
        myReader = csv.reader(csvfile, delimiter = ',')
        for row in myReader:
            sql = """INSERT INTO "%s" (%s) VALUES (%s)""" % (
                table, ','.join(cols),
                ','.join("'" + item.strip() + "'" for item in row))

            sql = sql.replace("'NULL'", 'NULL')

            #print 'sql: %s' % sql

            dbUtil.executeSQL(cursor, sql)

            cnt += 1
            if cnt % 10000 == 0:
                conn.commit()

    conn.commit()
    cnt = 0
