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

from kgtool.alg_graph import *  # noqa


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_file2abspath(self):
        dg = DirectedGraph([[0 ,1] ,[1 ,2] ,[3 ,4]])
        print dg.relation
        assert dg.relation=={0: [0, 1, 2], 1: [1, 2], 2: [2], 3: [3, 4], 4: [4]}

        dg =DirectedGraph([[0 ,1] ,[1 ,2] ,[2 ,3] ,[3 ,4]])
        print dg.relation
        assert dg.relation=={0: [0, 1, 2, 3, 4], 1: [1, 2, 3, 4], 2: [2, 3, 4], 3: [3, 4], 4: [4]}




if __name__ == '__main__':
    unittest.main()
