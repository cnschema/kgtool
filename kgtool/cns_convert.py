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
from cns_model import CnsSchema
from cns_common import gen_cns_id

# global constants
VERSION = 'v20180724'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
run_convert: convert non-cnSchema JSON into cns_item using loaded_schema properties
"""



def run_convert(cns_model, item, types, primary_keys, report = None):
    """
        property_alias  => property_name
        create @id
        assert @type
    """
    assert types
    #logging.info(json4debug(item))

    if primary_keys:
        assert type(primary_keys) == list

    cns_item = {
        "@type": types,
    }

    for p,v in item.items():
        template = cns_model.get_template_for_property_alias(types, p)
        if template:
            px = template["refProperty"]
            cns_item[px] = v
        else:
            bug = {
                "category": "warn_convert_cns",
                "description": "property not defined in schema",
                "property": p
            }

            if report is not None:
                report.report_bug(bug)


    if item.get("@id"):
        cns_item["@id"] = item["@id"]

    xid = gen_cns_id(cns_item, primary_keys)
    cns_item["@id"] = xid

    return cns_item


REGEX_JSON_STRING = re.compile(ur"^{.+}$")

def convert_cns_type_string(types):
    if isinstance(types, list):
        return types
    else:
        if types.startswith("["):
            return [x.strip() for x in types[1:-1].split(",")]
        elif isinstance(types, basestring):
            return types.split(",")
        else:
            assert False


def run_normalize_item(cns_model, cns_item, wm):
    """
        convert an item to norm value
    """
    types = cns_item["@type"]
    types = convert_cns_type_string(types)
    cns_item["@type"] = types

    for p,v in cns_item.items():
        v_new = run_normalize_value(cns_model, types, p, v, wm)
        if v_new:
            cns_item[p] = v_new

    return cns_item

def run_normalize_value(cns_model, types, p, v, wm):
    """
        convert value to norm value
    """
    if p in ["@type", "@id"]:
        return

    if isinstance(v, basestring):
        #json string
        if v.startswith("[") and v.endswith("]"):
            return json.loads(v)
        elif  v.startswith("{") and v.endswith("}"):
            return json.loads(v)

    for xtype in types:
        template = cns_model.index_validate_template.get(xtype,{}).get(p)
        if template:
            logging.info(json4debug(template))

            range_config = template["propertyRange"]
            if range_config["text"].lower() == "integer":
                return int(v)
            elif range_config["text"].lower() == "float":
                return float(v)
            elif range_config["text"].lower() == "number":
                return "{}".format(v)


def task_convert(args):
    logging.info( "called task_convert" )
    filename = "../schema/cns_top_v2.0.jsonld"
    filename = file2abspath(filename, __file__)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(filename)

    filename = args["input_file"]
    jsondata = file2json(filename)
    report = CnsBugReport()
    for idx, item in enumerate(jsondata):
        types = [item["mainType"], "Thing"]
        primary_keys = [idx]
        cns_item = run_convert(loaded_schema, item, types, primary_keys, report)
        logging.info(json4debug(cns_item))
        #loaded_schema.run_validate(cns_item, report)
    logging.info(json4debug(report.data))


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
