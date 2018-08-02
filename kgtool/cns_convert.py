#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Li Ding

# base packages
import os
import sys
import json
import logging
import codecs
import hashlib
import datetime
import time
import argparse
import urlparse
import re
import collections
import glob
import copy

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

from kgtool.core import *  # noqa
from kgtool.stats import stat_kg_report_per_item
from cns_model import CnsSchema, init_report,write_report,gen_cns_id

# global constants
VERSION = 'v20180724'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
run_convert: convert non-cnSchema JSON into cnsItem using loaded_schema properties
"""



def run_convert(cns_model, item, types, primary_keys, report = None):
    """
        property_alias  => property_name
        create @id
        assert @type
    """
    assert types
    if primary_keys:
        assert type(primary_keys) == list

    cnsItem = {
        "@type": types,
    }

    for p,v in item.items():
        px = cns_model.index_property_alias.get(p)
        if px:
            cnsItem[px] = v
        else:
            bug = {
                "category": "warn_convert_cns",
                "text": "property not defined in schema",
                "property": p
            }

            if report is not None:
                write_report(report, bug)


    if item.get("@id"):
        cnsItem["@id"] = item["@id"]

    xid = gen_cns_id(cnsItem, primary_keys)
    cnsItem["@id"] = xid

    return cnsItem



def task_convert(args):
    logging.info( "called task_convert" )
    filename = "../schema/cns_top.jsonld"
    filename = file2abspath(filename, __file__)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(filename)

    filename = args["input_file"]
    jsondata = file2json(filename)
    report = init_report()
    for idx, item in enumerate(jsondata):
        types = [item["mainType"], "Thing"]
        primary_keys = [idx]
        cnsItem = run_convert(loaded_schema, item, types, primary_keys, report)
        logging.info(json4debug(cnsItem))
        #loaded_schema.run_validate(cnsItem, report)
    logging.info(json4debug(report))


if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--input_schema': 'input schema',
        '--output_file': 'output file',
        '--debug_dir': 'debug directory',
        '--option': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""

    # task 2: convert
    python kgtool/run_convert.py task_convert --input_file=tests/test_cns_schema_input1.json --debug_dir=local/



"""
