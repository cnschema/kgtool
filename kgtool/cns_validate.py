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
from cns_model import preload_schema, CnsSchema, init_report,write_report

# global constants
VERSION = 'v20180724'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
* run_validate: validate integrity constraints imposed by template and property definition
   * class-property binding
   * property domain
   * property range
"""


def run_validate_recursive(loaded_schema, cnsTree, report):
    if type(cnsTree) == list:
        for cns_item in cnsTree:
            run_validate_recursive(loaded_schema, cns_item, report)
    elif type(cnsTree) == dict:
        run_validate(loaded_schema, cnsTree, report)
        run_validate_recursive(loaded_schema, cnsTree.values(), report)
    else:
        # do not validate
        pass


def run_validate(loaded_schema, cns_item, report):
    """
        validate the following
        * template restriction  (class-property binding)

        * range of property
    """
    report["stats"]["items_validated"] += 1

    if not _validate_system(loaded_schema, cns_item, report):
        return report

    _validate_class(loaded_schema, cns_item, report)

    _validate_template(loaded_schema, cns_item, report)

    _validate_range(loaded_schema, cns_item, report)

    _validate_domain(loaded_schema, cns_item, report)

    return report

def _validate_class(loaded_schema, cns_item, report):
    """
        if type is defined in schema
    """
    for xtype in cns_item["@type"]:
        has_type = False
        for schema in loaded_schema.loaded_schema_list:
            type_definition = schema.index_definition_alias.get(xtype)
            if type_definition:
                has_type =True
                break

        if not has_type:
            bug = {
                "category": "info_validate_class",
                "text": "class not defined",
                "class" : xtype,
                #"item": cns_item
            }
            write_report(report, bug)



def _validate_system(loaded_schema, cns_item, report):
    types = cns_item.get("@type")
    if "@vocab" in cns_item:
        bug = {
            "category": "info_validate_system",
            "text": "skip validating system @vocab",
        }
        write_report(report, bug)
        return False

    if not types:
        bug = {
            "category": "warn_validate_system",
            "text": "item missing @type",
            "item": cns_item
        }
        write_report(report, bug)
        return False

    return True

def _validate_range(loaded_schema, cns_item, report):
    #TODO only validate non object range for now

    TEXT_PROP = [""]
    for p in cns_item:
        if p in ["@context"]:
            #skip this range check
            bug = {
                "category": "info_validate_range",
                "text": "skip validating range @vocab",
                #"item": cns_item
            }
            write_report(report, bug)
            continue

        rangeExpect = loaded_schema.index_validate_range.get(p)
        if not rangeExpect:
            bug = {
                "category": "warn_validate_range",
                "text": "range not specified in schema",
                "property": p
            }
            write_report(report, bug)
            continue

        for v in json_get_list(cns_item, p):
            if "pythonTypeValue" in rangeExpect:
                rangeActual = type(v)
                if rangeActual in rangeExpect["pythonTypeValue"]:
                    # this case is fine
                    pass
                else:
                    bug = {
                        "category": "warn_validate_range",
                        "text": "range value datatype mismatch",
                        "property": p,
                        "expected" : rangeExpect["text"],
                        "actual" : str(rangeActual),
                    }
                    write_report(report, bug)
            else:
                if type(v)== dict:
                    rangeActual = v.get("@type",[])
                    if set(rangeExpect["cnsRange"]).intersection(rangeActual):
                        # this case is fine
                        pass
                    else:
                        bug = {
                            "category": "warn_validate_range",
                            "text": "range object missing types",
                            "property": p,
                            "expected" : rangeExpect["cnsRange"],
                            "actual" : rangeActual,
                        }
                        write_report(report, bug)
                else:
                    bug = {
                        "category": "warn_validate_range",
                        "text": "range value should be object",
                        "property": p,
                        "expected" : rangeExpect["cnsRange"],
                        "actual" : v,
                        #"item" : v,
                    }
                    write_report(report, bug)


def _validate_domain(loaded_schema, cns_item, report):
    # template validation
    validated_property = set()
    for p in cns_item:
        domainExpected = loaded_schema.index_validate_domain.get(p)
        if domainExpected == None:
            bug = {
                "category": "warn_validate_domain",
                "text": "domain not specified in schema",
                "property": p
            }
            write_report(report, bug)
            continue



        domainActual = cns_item.get("@type",[])
        for domain in domainActual:
            if not loaded_schema.index_definition_alias.get(domain):
                bug = {
                    "category": "warn_validate_definition",
                    "text": "class not defined in schema",
                    "class": domain
                }
                write_report(report, bug)

        if not domainActual:
            bug = {
                "category": "warn_validate_domain",
                "text": "domain not specified",
                "property": p,
                "item": cns_item
            }
            write_report(report, bug)
        elif set(domainExpected).intersection(domainActual):
            # this case is fine
            pass
        else:
            bug = {
                "category": "warn_validate_domain",
                "text": "domain unexpected",
                "property": p,
                "expected": domainExpected,
                "actual": domainActual
            }
            write_report(report, bug)

def _validate_template(loaded_schema, cns_item, report):
    # template validation
    validated_property = set()
    for xtype in cns_item["@type"]:
        for template in loaded_schema.index_validate_template[xtype]:
            p = template["refProperty"]
            if p in validated_property:
                continue
            else:
                validated_property.add(p)

            cardAcual = len(json_get_list(cns_item, p))

            if cardAcual < template["minCardinality"]:
                # logging.info(json4debug(template))
                # logging.info(json4debug(cns_item))
                # assert False
                bug = {
                    "category": "warn_validate_template",
                    "text": "minCardinality",
                    "property": p,
                    "expected": template["minCardinality"],
                    "actual": cardAcual,
                    "item_name": cns_item.get("name"),
                    "item_value": cns_item.get(p),
                }
                write_report(report, bug)


            if "maxCardinality" in template:
                if cardAcual > template["maxCardinality"]:
                    bug = {
                        "category": "warn_validate_template",
                        "text": "maxCardinality",
                        "property": p,
                        "expected": template["maxCardinality"],
                        "actual": cardAcual,
                        "item_name": cns_item.get("name"),
                        "item_value": cns_item.get(p),
                    }
                    write_report(report, bug)




def task_validate(args):
    logging.info( "called task_validate" )
    schema_filename = args.get("input_schema")
    if not schema_filename:
        schema_filename = "schema/cns_top.jsonld"

    preloadSchemaList = preload_schema(args)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(schema_filename, preloadSchemaList)

    filename = args["input_file"]
    if args.get("option") == "jsons":
        report = init_report()
        for idx, line in enumerate(file2iter(filename)):
            if idx % 10000 ==0:
                logging.info(idx)
                logging.info(json4debug(report))
            json_data = json.loads(line)
            run_validate_recursive(loaded_schema, json_data, report)
            stat_kg_report_per_item(json_data, None, report["stats"])
        logging.info(json4debug(report))

    else:
        jsondata = file2json(filename)
        report = init_report()
        run_validate_recursive(loaded_schema, jsondata, report)
        logging.info(json4debug(report))


if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--dir_schema': 'input schema',
        '--output_file': 'output file',
        '--debug_dir': 'debug directory',
        '--option': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    # task 3: validate
    python kgtool/cns_validate.py task_validate --input_file=schema/cns_top.jsonld --debug_dir=local/debug --dir_schema=schema
    python kgtool/cns_validate.py task_validate --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/debug --dir_schema=schema
    python kgtool/cns_validate.py task_validate --input_file=tests/test_cns_schema_input1.json --debug_dir=local/debug --dir_schema=schema

    python kgtool/cns_validate.py task_validate --input_file=tests/test_cns_schema_input1.json --debug_dir=local/debug --dir_schema=schema

"""
