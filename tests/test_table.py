#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from kgtool.core import file2abspath,json4debug  # noqa
from kgtool.table import *  # noqa


class TableTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_excel2json(self):
        filename = "ex2.xls"
        filename = file2abspath(filename, __file__)

        if not os.path.exists(filename):
            # init_excel():
            input_data = [{
                "name": u"张三",
                u"年龄": 18
            },
                {
                "name": u"李四",
                "notes": u"this is li si",
                u"年龄": 18
            }]
            json2excel(input_data, ["name", u"年龄", "notes"], filename)

        output_data = excel2json(filename)
        assert len(output_data) == 2
        assert len(output_data["data"]) == 1
        assert len(output_data["data"].values()[0]) == 2
        assert output_data["fields"].values()[0] == ["name", u"年龄", "notes"]

    def test_load_empty_sheet_excel2json2018(self):
        schema_excel_filename = "cns_empty.xlsx"
        schema_excel_filename = file2abspath(schema_excel_filename, __file__ )
        output_json = excel2json2018(schema_excel_filename)
        logging.info(json4debug(output_json))
        assert len(output_json) == 4
        assert len(output_json[0]['rows']) == 0

        schema_excel_filename = "empty_sheet.xls"
        schema_excel_filename = file2abspath(schema_excel_filename, __file__ )
        output_json = excel2json2018(schema_excel_filename)
        logging.info(json4debug(output_json))
        assert len(output_json) == 1
        assert len(output_json[0]['rows']) == 0
        assert len(output_json[0]['columns']) == 0

if __name__ == '__main__':
    unittest.main()
