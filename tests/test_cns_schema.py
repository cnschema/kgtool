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
        pass

    def test_import_jsonld(self):
        logging.info( "called task_excel2jsonld" )

        #validate if we can reproduce the same jsonld based on input
        jsonld_input = file2json(self.filenameSchema)

        jsonld_output = self.loaded_schema.export_jsonld()

        assert len(jsonld_input) == len(jsonld_output)
        x = json4debug(jsonld_input).split("\n")
        y = json4debug(jsonld_output).split("\n")
        for idx, line in enumerate(x):
            if x[idx] != y[idx]:
                logging.info(json4debug([idx, x[idx],y[idx]]) )
                break

    def test_run_convert(self):
        tin = "test_cns_schema_input1.json"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = init_report()
        for idx, item in enumerate(input):
            types = [ item["mainType"], "Thing" ]
            primary_keys = [ item.get("name", item.get(u"名称")) ]
            cns_item = run_convert(self.loaded_schema, item, types, primary_keys, report)
            logging.info(json4debug(cns_item))

            assert "name" in cns_item
            #assert "alternateName" in cns_item

            if idx == 0:
                # test sha256
                assert cns_item["@id"] == "66e830b5690eef238b3fb6eb5662d66b650f17a6980cfd5db11b11d8ea93b136"

        #assert False
        if len(report["bugs_sample"]) != 3:
            logging.info(json4debug(report))
            assert False, len(report["bugs_sample"])

    def test_run_convert2(self):
        filenameSchema = "../schema/cns_organization.jsonld"
        filenameSchema = file2abspath(filenameSchema)
        loaded_schema = CnsSchema()
        loaded_schema.import_jsonld(filenameSchema)

        item = {
            "changeAfter": "深圳金砖城市国开先导基金管理有限公司",
            "changeBefore": "深圳金砖城市国开先导基金管理有限公司",
            "changeItem": "负责人变更（法定代表人、负责人、首席代表、合伙事务执行人等变更）变更",
            "date": "2015-09-25"
        }
        types = ["CompanyInfoUpdateEvent", "Event", "Thing"]
        item['name'] = '{0}_{1}_{2}'.format("aaa", item['date'], item['changeItem'])
        primary_keys = [ item["name"] ]
        report = init_report()
        cns_item = run_convert(loaded_schema, item, types, primary_keys, report)
        #logging.info(json4debug(cns_item))
        logging.info(json4debug(report))

        assert "changeCategory" in cns_item

    def test_run_convert_cns_link(self):
        filenameSchema = "../schema/cns_organization.jsonld"
        filenameSchema = file2abspath(filenameSchema)
        loaded_schema = CnsSchema()
        loaded_schema.import_jsonld(filenameSchema)

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

        report = init_report()

        entities = []
        types = ["Company", "Thing"]
        item_in = {}
        item_in['name'] = item["cName"]
        primary_keys = [ item_in["name"] ]
        cns_item_in = run_convert(loaded_schema, item_in, types, primary_keys, report)
        entities.append( cns_item_in )

        types = ["Person", "Thing"]
        item_out = {}
        item_out['name'] = item["legalPerson"]
        primary_keys = [ item_in['name'], item_out["name"] ]
        cns_item_out = run_convert(loaded_schema, item_out, types, primary_keys, report)
        entities.append( cns_item_out )

        types = ["LegalRepresentativeRole", "CnsLink", "Thing"]
        item_link = {}
        item_link['in'] = cns_item_in["@id"]
        item_link['out'] = cns_item_out["@id"]

        primary_keys = [ ]
        cns_item_link = run_convert(loaded_schema, item_link, types, primary_keys, report)
        entities.append( cns_item_link )

        logging.info(json4debug(entities))
        logging.info(json4debug(report))
        assert cns_item_link["@id"] == "b11ab8dbd506a271791a4a5813e2684fa592377399fe239a1b21edf304b9f312"
        assert cns_item_in["@id"] == "b6a7801587af217eba42da036c2659696f6153aff2d7df14e39f74e6f2672fef"
        assert cns_item_out["@id"] == "09cd7eb1132c9de9cef0bd0c3b534586220f8c7f72186f1db0404da1a725301a"
        #assert False



    def test_gen_cns_id(self):
        cns_item = {
        }
        try:
            gen_cns_id(cns_item)
            assert False
        except:
            pass

        cns_item = {
            "@type": ["CnsLink", "Thing"],
            "in": "b6a7801587af217eba42da036c2659696f6153aff2d7df14e39f74e6f2672fef" ,
            "out": "09cd7eb1132c9de9cef0bd0c3b534586220f8c7f72186f1db0404da1a725301a" ,
        }
        id_link = gen_cns_id(cns_item)
        assert id_link == "79841891d32addca19313d0bce462c7fcbb6e6b94e3276ca0402b9213410cf4d", id_link

        cns_item = {
            "@type": ["CnsLink", "Thing"],
            "in": "b6a7801587af217eba42da036c2659696f6153aff2d7df14e39f74e6f2672fef" ,
            "out": "09cd7eb1132c9de9cef0bd0c3b534586220f8c7f72186f1db0404da1a725301a" ,
            "identifier": "addabc" ,
        }
        id_link = gen_cns_id(cns_item)
        assert id_link == "3ed801c73765e96fb5895069d392245a4fbd340142e96f0ed5bdf195b2259945", id_link

        cns_item = {
            "@type": ["CnsLink", "Thing"],
            "in": "b6a7801587af217eba42da036c2659696f6153aff2d7df14e39f74e6f2672fef" ,
            "out": "09cd7eb1132c9de9cef0bd0c3b534586220f8c7f72186f1db0404da1a725301a" ,
            "identifier": "addabc" ,
        }
        primary_keys = ["123","345"]
        id_link = gen_cns_id(cns_item, primary_keys)
        assert id_link == "2a5943be7ec660a256b58b22754d9d8a27303b12c4c1a13456aead0a8c179a11", id_link

        cns_item = {
            "@type": ["CnsLink", "Thing"],
            "in": "b6a7801587af217eba42da036c2659696f6153aff2d7df14e39f74e6f2672fef" ,
            "out": "09cd7eb1132c9de9cef0bd0c3b534586220f8c7f72186f1db0404da1a725301a" ,
            "identifier": "addabc" ,
        }
        primary_keys = {"123":"345"}
        id_link = gen_cns_id(cns_item, primary_keys)
        assert id_link == "9841722f1ac4defdef21678550eb4d700a05d2d4b6bd99a93f3656adf6cb1851", id_link


    def test_cns_validate(self):
        tin = "test_cns_schema_input1.json"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = init_report()
        for item in input:
            types = [ item["mainType"], "Thing" ]
            primary_keys = [ item.get("name", item.get(u"名称")) ]
            cns_item = run_convert(self.loaded_schema, item, types, primary_keys)
            logging.info(json4debug(cns_item))
            run_validate(self.loaded_schema, cns_item, report, True)

        if len(report["bugs_sample"]) != 3:
            logging.info(json4debug(report))
            assert False, len(report["bugs_sample"])

    def test_normalize_value(self):
        cns_item ={
            "@type": ["QuantitativeValue","CnsDataStructure"],
            "value": "1.6",
            "unitText": u"元",
        }
        assert isinstance(cns_item["value"], basestring)
        wm = {}
        run_normalize_item(self.loaded_schema, cns_item, wm)
        assert isinstance(cns_item["value"], float)

        cns_item ={
            "@type": ["QuantitativeValue","CnsDataStructure"],
            "value": ["1.6"],
            "unitText": u"元",
        }
        assert isinstance(cns_item["value"], list)
        wm = {}
        try:
            run_normalize_item(self.loaded_schema, cns_item, wm)
            assert False
        except:
            pass

        cns_item ={
            "@type": ["QuantitativeValue","CnsDataStructure"],
            "value": 1,
            "unitText": u"元",
        }
        assert isinstance(cns_item["value"], int)
        wm = {}
        run_normalize_item(self.loaded_schema, cns_item, wm)
        assert isinstance(cns_item["value"], float)

        cns_item ={
            "@type": ["CnsLink", "QuantitativeValue","CnsDataStructure"],
            "value": 1,
            "unitText": u"元",
        }
        assert isinstance(cns_item["value"], int)
        wm = {}
        run_normalize_item(self.loaded_schema, cns_item, wm)
        assert isinstance(cns_item["value"], float)


        cns_item ={
            "@type": ["QuantitativeValue","CnsDataStructure"],
            "value": "100万",
            "unitText": u"元",
        }
        assert isinstance(cns_item["value"], basestring)
        wm = {}
        try:
            run_normalize_item(self.loaded_schema, cns_item, wm)
            assert False
        except:
            pass

        cns_item ={
            "@type": "[QuantitativeValue, CnsDataStructure]",
            "value": 1,
            "unitText": u"元",
        }
        assert isinstance(cns_item["@type"], basestring)
        assert isinstance(cns_item["value"], int)
        wm = {}
        run_normalize_item(self.loaded_schema, cns_item, wm)
        assert isinstance(cns_item["value"], float)
        assert isinstance(cns_item["@type"], list)

        cns_item ={
            "@type": "QuantitativeValue",
            "value": 1,
            "unitText": u"元",
        }
        assert isinstance(cns_item["@type"], basestring)
        assert isinstance(cns_item["value"], int)
        wm = {}
        run_normalize_item(self.loaded_schema, cns_item, wm)
        assert isinstance(cns_item["value"], float)
        assert isinstance(cns_item["@type"], list)


    def test_iso8601_parse(self):
        v = 1
        ret = iso8601_date_parse(v)
        assert ret == None, v

        v = []
        ret = iso8601_datetime_parse(v)
        assert ret == None, v

        v = "至今"
        ret = iso8601_datetime_parse(v)
        assert ret == None, v

        v = u"至今"
        ret = iso8601_datetime_parse(v)
        assert ret == None, v

        v = "1990-01-02"
        ret = iso8601_date_parse(v)
        assert ret != None, v

        v = "1990-01-02T00:10:01"
        ret = iso8601_date_parse(v)
        assert ret == None, v

        v = "1990-01-02"
        ret = iso8601_datetime_parse(v)
        assert ret == None, v

        v = "1990-01-02T00:10:01"
        ret = iso8601_datetime_parse(v)
        assert ret != None, v

        v = "1990-01-02T00:10:01Z"
        ret = iso8601_datetime_parse(v)
        assert ret == None, v

        v = "1990-01-02T00:10:01.123456"
        ret = iso8601_datetime_parse(v)
        assert ret == None, v

    def test_run_validate_recursive(self):
        tin = "../schema/cns_top.jsonld"
        tin = file2abspath(tin, __file__)
        input = file2json(tin)

        report = init_report()
        run_validate_recursive(self.loaded_schema, input, report)


        for cns_item in input["@graph"]:
            assert isinstance(cns_item.get("alternateName",[]), list) , cns_item.get("alternateName")


        #assert False
        if len(report["bugs_sample"]) != 2:
            logging.info(json4debug(report))
            assert False, len(report["bugs_sample"])


if __name__ == '__main__':
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    unittest.main()
