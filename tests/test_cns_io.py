#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os
import sys
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from cns.cns_io import *  # noqa
from kgtool.core import *  # noqa
from kgtool.cns_convert import *  # noqa
from kgtool.cns_model import *  # noqa
from kgtool.cns_validate import *  # noqa


class CoreTestCase(unittest.TestCase):

    def test_load_empty_sheet(self):
        schema_excel_filename = "cns_empty.xlsx"
        schema_excel_filename = file2abspath(schema_excel_filename, __file__ )
        options = "jsonld,table_single,table_import,dot_compact,dot_import,dot_full"
        output_json = excel2schema(schema_excel_filename, None, options)
        logging.info(json4debug(output_json))
        assert not output_json["validation_result"]
        #assert False
