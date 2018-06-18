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
from kgtool.stats import *  # noqa


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_statJsonld(self):
        tin = "test_stats_kg1.jsonld"
        tout = file2abspath(tin, __file__)
        with open(tout) as f:
            data = json.load(f)
            ret = stat_jsonld(data)
            print json.dumps(ret)
            assert ret["triple"] == 29
            assert ret[u"tag_抒情"] == 1

    def test_stat_jsonld(self):
        tin = "test_stats_kg1.jsonld"
        tout = file2abspath(tin, __file__)
        with open(tout) as f:
            data = json.load(f)
            ret = stat_jsonld(data)
            print json.dumps(ret)
            assert ret["triple"] == 29
            assert ret[u"tag_抒情"] == 1

    def stat_sample(self):
        tin = "test_stats_kg1.jsonld"
        tout = file2abspath(tin, __file__)
        with open(tout) as f:
            data = json.load(f)
            data = [data]
            ret = stat_samples(data)
            print json4debug(ret)
            #raise("aa")

    def test_stat_table(self):
        table = [{u"名称": u"张三", u"年龄": u"13.0"}, {u"名称": u"李四", u"年龄": u"20"}]
        ret = stat_table(table,[u"名称", u"年龄"],[u"名称", u"年龄"])

    def test_stat_kg_pattern(self):
        tin = "test_stats_kg1.jsonld"
        tout = file2abspath(tin, __file__)
        with open(tout) as f:
            data = json.load(f)
            ret = stat_kg_pattern(data)
            print json4debug(ret)
            #raise("aa")


if __name__ == '__main__':
    unittest.main()
