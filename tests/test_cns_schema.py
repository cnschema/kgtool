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

from kgtool.core import *  # noqa
from kgtool.cns_schema import *  # noqa


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        filenameSchema = "../schema/cns-thing-18q3.jsonld"
        self.filenameSchema = file2abspath(filenameSchema)
        self.cnsSchema = CnsSchema()
        self.cnsSchema.importJsonLd(self.filenameSchema)
        pass

    def test_loadJsonld(self):
        logging.info( "called task_excel2jsonld" )

        #validate if we can reproduce the same jsonld based on input
        jsonld_input = file2json(self.filenameSchema)

        jsonld_output = self.cnsSchema.exportJsonLd()

        assert len(jsonld_input) == len(jsonld_output)
        x = json4debug(jsonld_input).split("\n")
        y = json4debug(jsonld_output).split("\n")
        for idx, line in enumerate(x):
            if x[idx] != y[idx]:
                logging.info(json4debug([idx, x[idx],y[idx]]) )
                break

    def test_cnsConvert(self):
        tin = "test_cns_schema_input1.json"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = self.cnsSchema.initReport()
        for item in input:
            types = [ item["mainType"], "Thing" ]
            primaryKeys = [ item.get("name", item.get(u"名称")) ]
            cnsItem = self.cnsSchema.cnsConvert(item, types, primaryKeys, report)
            logging.info(json4debug(cnsItem))

            assert "name" in cnsItem
            assert "alternateName" in cnsItem
        #assert False
        if len(report["bugs"]) != 4:
            logging.info(json4debug(report))
            assert False, len(report["bugs"])

    def test_cnsValidate(self):
        tin = "test_cns_schema_input1.json"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = self.cnsSchema.initReport()
        for item in input:
            types = [ item["mainType"], "Thing" ]
            primaryKeys = [ item.get("name", item.get(u"名称")) ]
            cnsItem = self.cnsSchema.cnsConvert(item, types, primaryKeys)
            logging.info(json4debug(cnsItem))
            self.cnsSchema.cnsValidate(cnsItem, report)

        if len(report["bugs"]) != 10:
            logging.info(json4debug(report))
            assert False, len(report["bugs"])

    def test_cnsValidateRecursive(self):
        tin = "../schema/cns-thing-18q3.jsonld"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = self.cnsSchema.initReport()
        self.cnsSchema.cnsValidateRecursive(input, report)

        #assert False
        if len(report["bugs"]) != 2:
            logging.info(json4debug(report))
            assert False, len(report["bugs"])


if __name__ == '__main__':
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    unittest.main()
