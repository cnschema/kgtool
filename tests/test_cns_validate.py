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
        filenameSchema = "../schema/cns_top_v2.0.jsonld"
        self.filenameSchema = file2abspath(filenameSchema)
        self.loaded_schema = CnsSchema()
        self.loaded_schema.jsonld2mem4file(self.filenameSchema)

        filenameSchema = "../schema/cns_organization_v2.0.jsonld"
        filenameSchema = file2abspath(filenameSchema)
        self.loaded_schema_org = CnsSchema()
        self.loaded_schema_org.jsonld2mem4file(filenameSchema)

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

        report = self.loaded_schema_org.report
        run_validate_recursive(self.loaded_schema_org, input, report)
        logging.info(json4debug(report.data))
        assert report.data["xtemplate"]["cp_Person_Thing_name"] == 2
        assert report.data["xtemplate"]["type_all_Person"] == 2
        assert report.data["xtemplate"]["cp_Thing_Thing_name"] == 1

        # two different main type should not co-exist
        assert not "cp_Person_Organization_city" in report.data["xtemplate"]
        assert "cp_Organization_Organization_city" in report.data["xtemplate"]


    def test_validate_null(self):
        input = [{
            "@id": "123",
            "name": None,
            "@type":["CnsTag","Thing"]
            }
        ]

        report = self.loaded_schema_org.report
        run_validate_recursive(self.loaded_schema_org, input, report)
        logging.info(json4debug(report.data))
        assert len(report.data["bugs_sample"])==1
        assert report.data["stats"]["warn_validate_datatype | range value datatype mismatch | CnsTag | name"]==0
        assert report.data["stats"]["warn_validate_template_regular | minCardinality | CnsTag | name"] == 1
