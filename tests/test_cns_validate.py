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

from kgtool.core import *  # noqa
from kgtool.cns_convert import *  # noqa
from kgtool.cns_model import *  # noqa
from kgtool.cns_validate import *  # noqa


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        filenameSchema = "../schema/cns_top.jsonld"
        self.filenameSchema = file2abspath(filenameSchema)
        self.loaded_schema = CnsSchema()
        self.loaded_schema.import_jsonld(self.filenameSchema)

        filenameSchema = "../schema/cns_organization.jsonld"
        filenameSchema = file2abspath(filenameSchema)
        self.loaded_schema_org = CnsSchema()
        self.loaded_schema_org.import_jsonld(filenameSchema)

        pass

    def test_validate_main_type(self):
        input = [{
            "@id": "123",
            "name":"a",
            "@type":["Organization","Thing","Person"]
            },
            {
            "@id": "456",
            "name":"b",
            "@type":["Person","Thing"]
            },
            {
            "@id": "456",
            "name":"c",
            "@type":["Thing"]
            }
        ]

        report = init_report()
        run_validate_recursive(self.loaded_schema_org, input, report)
        logging.info(json4debug(report))
        assert report["xtemplate"]["cp_Person_Thing_name"] == 2
        assert report["xtemplate"]["type_all_Person"] == 2
        assert report["xtemplate"]["cp_Thing_Thing_name"] == 1

    def test_validate_null(self):
        input = [{
            "@id": "123",
            "name": None,
            "@type":["CnsTag","Thing"]
            }
        ]

        report = init_report()
        run_validate_recursive(self.loaded_schema_org, input, report)
        logging.info(json4debug(report))
        assert len(report["bugs_sample"])==1
        assert report["stats"]["warn_validate_datatype | range value datatype mismatch | CnsTag | name"]==0
        assert report["stats"]["warn_validate_template_regular | minCardinality | CnsTag | name"] == 1
