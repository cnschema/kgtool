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
from cns.cns_schema import *  # noqa


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        filenameSchema = "../schema/cns_top.jsonld"
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
        for idx, item in enumerate(input):
            types = [ item["mainType"], "Thing" ]
            primary_keys = [ item.get("name", item.get(u"名称")) ]
            cns_item = self.cnsSchema.cnsConvert(item, types, primary_keys, report)
            logging.info(json4debug(cns_item))

            assert "name" in cns_item
            #assert "alternateName" in cns_item

            if idx == 0:
                # test sha256
                assert cns_item["@id"] == "2a943ed124ead6a1cd87f8130bbbe247c76ddc7d502d8dd1e1c562bc13b74824"

        #assert False
        if len(report["bugs"]) != 4:
            logging.info(json4debug(report))
            assert False, len(report["bugs"])

    def test_cnsConvert2(self):
        filenameSchema = "../schema/cns_organization.jsonld"
        filenameSchema = file2abspath(filenameSchema)
        cnsSchema = CnsSchema()
        cnsSchema.importJsonLd(filenameSchema)

        item = {
            "changeAfter": "深圳金砖城市国开先导基金管理有限公司",
            "changeBefore": "深圳金砖城市国开先导基金管理有限公司",
            "changeItem": "负责人变更（法定代表人、负责人、首席代表、合伙事务执行人等变更）变更",
            "date": "2015-09-25"
        }
        types = ["CompanyInfoUpdateEvent", "Event", "Thing"]
        item['name'] = '{0}_{1}_{2}'.format("aaa", item['date'], item['changeItem'])
        primary_keys = [ item["name"] ]
        report = cnsSchema.initReport()
        cns_item = cnsSchema.cnsConvert(item, types, primary_keys, report)
        #logging.info(json4debug(cns_item))
        logging.info(json4debug(report))

        assert "changeCategory" in cns_item

    def test_cnsConvertCnsLink(self):
        filenameSchema = "../schema/cns_organization.jsonld"
        filenameSchema = file2abspath(filenameSchema)
        cnsSchema = CnsSchema()
        cnsSchema.importJsonLd(filenameSchema)

        item = {
            "business": "房地产开发与经营；室内、外工程装饰装修工程；物业服务；房地产信息咨询服务",
            "cName": "塔城宏源时代房地产开发有限公司",
            "city": "塔城地区",
            "credId": "91654201072210066B",
            "desc": "房地产开发与经营；室内、外工程装饰装修工程；物业服务；房地产信息咨询服务",
            "establishDate": "2013-06-27",
            "indChain": [
                [
                    {
                        "id": "32",
                        "namne": "房地产产业链"
                    }
                ]
            ],
            "industry": [
                {
                    "industryId": "209",
                    "industyrName": "房地产开发"
                }
            ],
            "label": [
                "OthersCompany"
            ],
            "legalPerson": "石磊",
            "orgType": "有限责任公司（自然人投资或控股的法人独资）",
            "province": "新疆维吾尔自治区",
            "regAddr": "新疆塔城地区塔城市解放路花园二期",
            "regCap": 1000,
            "regStatus": "开业",
            "seniors": [
                {
                    "name": "石磊",
                    "position": "执行董事兼总经理"
                }
            ],
            "shareHolders": [
                {
                    "money": 1000,
                    "name": "塔城古镇商业投资管理有限公司",
                    "ratio": 1,
                    "type": 1
                }
            ]
        }
        item = any2unicode(item)

        report = cnsSchema.initReport()

        entities = []
        types = ["Company", "Thing"]
        item_in = {}
        item_in['name'] = item["cName"]
        primary_keys = [ item_in["name"] ]
        cns_item_in = cnsSchema.cnsConvert(item_in, types, primary_keys, report)
        entities.append( cns_item_in )

        types = ["Person", "Thing"]
        item_out = {}
        item_out['name'] = item["legalPerson"]
        primary_keys = [ item_in['name'], item_out["name"] ]
        cns_item_out = cnsSchema.cnsConvert(item_out, types, primary_keys, report)
        entities.append( cns_item_out )

        types = ["LegalRepresentativeRole", "CnsLink", "Thing"]
        item_link = {}
        item_link['in'] = cns_item_in["@id"]
        item_link['out'] = cns_item_out["@id"]

        primary_keys = [ ]
        cns_item_link = cnsSchema.cnsConvert(item_link, types, primary_keys, report)
        entities.append( cns_item_link )

        logging.info(json4debug(entities))
        logging.info(json4debug(report))
        assert cns_item_link["@id"] == "fb69f08c76f8ca5f0506a3c24c6fe57b443ab54d4d49fdbff75b76bb11bd37df"
        assert cns_item_in["@id"] == "5376521713a9d22a50eeebbcc3bb6b3d9dd46ca371b998ac1a22fab20ff40c28"
        assert cns_item_out["@id"] == "730ef5ad457ed91bcafde8a4d00e53fca87ff994a37dae02a5efe9666cf5bf4c"
        #assert False

    def test_cnsValidate(self):
        tin = "test_cns_schema_input1.json"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = self.cnsSchema.initReport()
        for item in input:
            types = [ item["mainType"], "Thing" ]
            primary_keys = [ item.get("name", item.get(u"名称")) ]
            cns_item = self.cnsSchema.cnsConvert(item, types, primary_keys)
            logging.info(json4debug(cns_item))
            self.cnsSchema.cnsValidate(cns_item, report)

        if len(report["bugs"]) != 8:
            logging.info(json4debug(report))
            assert False, len(report["bugs"])

    def test_cnsValidateRecursive(self):
        tin = "../schema/cns_top.jsonld"
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
