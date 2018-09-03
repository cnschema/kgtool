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


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_file2abspath(self):
        tin = "test.json"
        tout = file2abspath(tin, __file__)
        logging.info(" {} => {}".format(tin, tout))
        assert tout.endswith(u"tests/" + tin), tout

        tin = "../test.json"
        tout = file2abspath(tin)
        logging.info(" {} => {}".format(tin, tout))
        assert tout.endswith(
            u"kgtool/" + os.path.basename(tin)), tout

    def test_file2json(self):
        filename = "test_core_file.json"
        filename = file2abspath(filename, __file__)
        ret = file2json(filename)
        assert len(ret) == 3

    def test_file2iter(self):
        filename = "test_core_file.json"
        filename = file2abspath(filename, __file__)
        str_iter = file2iter(filename)
        assert len(list(str_iter)) == 5

    def test_json_get(self):

        json_data = {"a": {"b": 1}, "c": ["d"], "e": "f"}
        assert type(json_get(json_data, ["a"])) == dict
        assert json_get(json_data, ["k"]) is None
        assert json_get(json_data, ["k"], 10) == 10
        assert json_get(json_data, ["a", "b"], 10) == 1
        assert json_get(json_data, ["a", "k"], 10) == 10
        assert json_get(json_data, ["c", "d"], 10) is None
        assert json_get(json_data, ["e", "k"], 10) is None
        assert type(json_get(json_data, ["c"])) == list

        json_data = {
            "father": {"name": "john"},
            "birthPlace": "Beijing"
        }

        assert json_get(json_data, ["father", "name"]) == "john"
        assert json_get(json_data, ["father", "image"], default="n/a") == "n/a"
        assert json_get(json_data, ["father", "father"]) is None
        assert json_get(json_data, ["birthPlace"]) == "Beijing"
        assert json_get(
            json_data, ["birthPlace", "name"], default="n/a") is None

    def test_json_get_list(self):

        json_data = {
            "name": "john",
            "age": None,
            "birthPlace": ["Beijing"]
        }
        assert json_get_list(json_data, "name") == ["john"]
        assert json_get_list(json_data, "birthPlace") == ["Beijing"]
        assert json_get_list(json_data, "age") == []


    def test_json_get_first_item(self):

        json_data = {
            "name": "john",
            "birthPlace": ["Beijing"],
            "interests": []
        }
        assert json_get_first_item(json_data, "name") == "john"
        assert json_get_first_item(json_data, "birthPlace") == "Beijing"
        assert json_get_first_item(json_data, "birthDate") == ''
        assert json_get_first_item(json_data, "interests", defaultValue=None) is None

    def test_json_append(self):

        json_data = {
            "name": "john",
            "birthPlace": ["Beijing"],
            "interests": []
        }

        json_append(json_data, "name", "a")
        assert json_data["name"] == "john"

        json_append(json_data, "birthPlace", "a")
        assert json_data["birthPlace"] == ["Beijing","a"]

        json_append(json_data, "keywords", "a")
        assert json_data["keywords"] == ["a"]

    def test_any2utf8(self):
        tin = "你好世界"
        tout = any2utf8(tin)
        logging.info(" {} => {}".format(tin, tout))

        tin = u"你好世界"
        tout = any2utf8(tin)
        logging.info((tin, tout))

        tin = "hello world"
        tout = any2utf8(tin)
        logging.info((tin, tout))

        tin = ["hello", "世界"]
        tout = any2utf8(tin)
        logging.info((tin, tout))

        tin = {"hello": u"世界"}
        tout = any2utf8(tin)
        logging.info((tin, tout))

        tin = {"hello": u"世界", "number": 90}
        tout = any2utf8(tin)
        logging.info((tin, tout))

    def test_any2unicode(self):
        tin = "你好世界"
        tout = any2unicode(tin)
        logging.info((tin, tout))

        tin = u"你好世界"
        tout = any2unicode(tin)
        logging.info((tin, tout))

        tin = "hello world"
        tout = any2unicode(tin)
        logging.info((tin, tout))

        tin = ["hello", "世界"]
        tout = any2unicode(tin)
        logging.info((tin, tout))

        tin = {"hello": u"世界"}
        tout = any2unicode(tin)
        logging.info((tin, tout))

    def test_any2sha256(self):
        tin = "你好世界"
        tout = any2sha256(tin)
        assert "beca6335b20ff57ccc47403ef4d9e0b8fccb4442b3151c2e7d50050673d43172" == tout, tout

    def test_any2sha1(self):
        tin = "你好世界"
        tout = any2sha1(tin)
        assert "dabaa5fe7c47fb21be902480a13013f16a1ab6eb" == tout, tout

        tin = u"你好世界"
        tout = any2sha1(tin)
        assert "dabaa5fe7c47fb21be902480a13013f16a1ab6eb" == tout, tout

        tin = "hello world"
        tout = any2sha1(tin)
        assert "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed" == tout, tout

        tin = ["hello", "world"]
        tout = any2sha1(tin)
        assert "2ed0a51bbdbc4f57378e8c64a1c7a0cd4386cc09" == tout, tout

        tin = {"hello": "world"}
        tout = any2sha1(tin)
        assert "d3b09abe30cfe2edff4ee9e0a141c93bf5b3af87" == tout, tout

    def test_json_dict_copy(self):
        property_list = [
            { "name":"name", "alternateName": ["name","title"]},
            { "name":"birthDate", "alternateName": ["dob","dateOfBirth"] },
            { "name":"description" }
        ]
        json_object = {"dob":"2010-01-01","title":"John","interests":"data","description":"a person"}
        ret = json_dict_copy(json_object, property_list)
        assert json_object["title"] == ret["name"]
        assert json_object["dob"] == ret["birthDate"]
        assert json_object["description"] == ret["description"]
        assert ret.get("interests") is None

    def test_parse_list_value(self):
        ret = parse_list_value(u"原文，正文")
        assert len(ret) == 2






if __name__ == '__main__':
    unittest.main()
