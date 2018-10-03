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

from core import *  # noqa
from stats import stat_kg_report_per_item
from cns_convert import convert_cns_type_string
from cns_model import preload_schema, CnsSchema

# global constants
VERSION = 'v20180724'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
given an CNS instance, validate integrity constraints imposed by template and property definition

current validation logic
1. basic validation
   * presence of @type
2. _rewrite_item
   * @type must be a list of string, not a string`
   * class not defined in schema or imported schema
   * property not defined in schema or imported schema
3. _validate_system_property
   * if Thing in @type, check if @id present
4. UCP template definition
   * undefined class-property binding, unable to find a template for this property based on any classes defined in @type
5. CP Range  template range
    5.1 _validate_entity_ref
       * value type missing
       * value mismatch
    5.2 _validate_datatype
        1. Date(IOS8601)  2018-01-20
        2. Datetime(IOS8601)   2018-01-20T09:00:00,   2018-01-20,   2018-01-20T09:00:00.234212,   2018-01-20T09:00:00Z
        3. Int
        4. Float
        5. Text
    5.3 _validate_datastructure
        value range not specified as datastructure in Schema
6. CP tempalte cardinality
    1. minCard    each instance of MutualFund should have at least one fundCode
    2. maxCard    each instance of MutualFund should have at most one fundCode

"""


def run_validate_recursive(loaded_schema, cns_item, report):
    if type(cns_item) == list:
        for v in cns_item:
            run_validate_recursive(loaded_schema, v, report)
    elif type(cns_item) == dict:
        if not "@id" in cns_item:
            return
        run_validate(loaded_schema, cns_item, report)
        for p,v in cns_item.items():
            if p in ["@context","in","out"]:
                continue
            run_validate_recursive(loaded_schema, v, report)


XTEMPLATE = "xtemplate"

def run_validate(loaded_schema, cns_item, report):
    """
        validate the following
        * template restriction  (class-property binding)

    """
    #stats
    report.data["stats"]["items_validate"] += 1

    #check types
    types = cns_item.get("@type")
    if not types:
        bug = {
            "category": "warn_validate",
            "description": "missing @type and no expected @type",
            "item": cns_item
        }
        report.report_bug(bug)
        return report

    _rewrite_item(loaded_schema, cns_item, report)

    _count_cnslink(loaded_schema, cns_item, report)

    _validate_system_property(loaded_schema, cns_item, report)

    _validate_template(loaded_schema, cns_item, cns_item["@type"], report)

    #_validate_range(loaded_schema, cns_item, report)

    #_validate_domain(loaded_schema, cns_item, report)

    return report

SYSTEM_PROPERTY_LIST = ["@context","@vocab", "@graph", "@id", "@type"]
def get_system_property():
    return SYSTEM_PROPERTY_LIST

def _rewrite_item(loaded_schema, cns_item, report):
    """
        fix bugs in item, keep on validation
    """

    # rewrite type
    types = cns_item.get("@type")
    if not isinstance(types, list):
        bug = {
            "category": "warn_rewrite_item",
            "description": " @type got string value",
            "item": cns_item
        }
        report.report_bug(bug)

        types = convert_cns_type_string(types)
        #rewrite type
        cns_item["@type"] = types

    types = cns_item.get("@type")
    if types is None:
        return

    #remove undefined type
    types_new = []
    for xtype in types:
        has_definition = False
        for schema in loaded_schema.imported_schema:
            the_definition = schema.get_definition_by_alias(xtype)
            if the_definition:
                has_definition =True
                break

        if not has_definition:
            bug = {
                "category": "warn_rewrite_item",
                "description": "class not defined",
                "class" : xtype,
                #"item": cns_item
            }
            report.report_bug(bug)
        else:
            types_new.append(xtype)
    cns_item["@type"] = types_new

    #undefined property
    # bad_property_list = []
    # for property in cns_item:
    #     if property in get_system_property():
    #         continue
    #
    #     has_definition = False
    #     for schema in loaded_schema.imported_schema:
    #         the_definition = schema.get_definition_by_alias(property)
    #         if the_definition:
    #             has_definition =True
    #             break
    #
    #     if not has_definition:
    #         bug = {
    #             "category": "warn_rewrite_item",
    #             "description": "property not defined",
    #             "property" : property,
    #             #"item": cns_item
    #         }
    #         report.report_bug(bug)
    #         bad_property_list.append(property)
    #
    # for p in bad_property_list:
    #     del cns_item[p]


def _validate_system_property(loaded_schema, cns_item, report):

    # system property
    types = cns_item["@type"]
    if "Thing" in types:
        if not "@id" in cns_item:
            bug = {
                "category": "warn_validate_system_property",
                "description": "instance of [Thing] missing @id",
                "item": cns_item
            }
            report.report_bug(bug)


def _count_cnslink(loaded_schema, cns_item, report):
    types = cns_item["@type"]
    if "CnsLink" in types:
        key_cnslink = u"cnslink_total"
        report.data[XTEMPLATE][key_cnslink] += 1

        if not isinstance(cns_item["in"], dict):
            key_cnslink = u"cnslink_{}".format(types[0])
            report.data[XTEMPLATE][key_cnslink] += 1

        else:
            main_type_in = cns_item["in"]["@type"][0]
            main_type_out = cns_item["out"]["@type"][0]

            key_cnslink = u"cnslink_{}_{}_{}".format(main_type_in, types[0], main_type_out)
            report.data[XTEMPLATE][key_cnslink] += 1



def _validate_template(loaded_schema, cns_item, types, report):
    # template validation
    validated_property = set()

    if _validate_template_special(loaded_schema, cns_item, types, report, validated_property):
        return

    _validate_template_regular(loaded_schema, cns_item, types, report, validated_property)


def _validate_template_special(loaded_schema, cns_item, types, report, validated_property):
    #special case
    main_type = types[0]
    if "CnsLink" in types and re.search(r"^[a-z]", main_type):
        if not isinstance(cns_item["in"], dict):
            return False

        types_domain = json_get_list(cns_item["in"], "@type")
        for xtype in types_domain:
            template_map = loaded_schema.index_validate_template.get(xtype)
            if template_map is None or len(template_map)==0:
                continue

            template = template_map.get(main_type)

            if template:
                v = cns_item["out"]
                range_actual = type(v)
                range_config = template["propertyRange"]
                type_actual = _validate_entity_ref(xtype, main_type, v, range_actual, range_config, report)
                validated_property.add(main_type)
                return True


def _validate_template_regular(loaded_schema, cns_item, types, report, validated_property):
    #regular validation
    for idx, xtype in enumerate(types):
        # only count main type's  template
        key_c = u"type_all_{}".format(xtype)
        report.data[XTEMPLATE][key_c] += 1
        #if idx == 0:
        #    key_c = u"type_first_{}".format(xtype)
        #    report.data[XTEMPLATE][key_c] += 1

        #find templates
        template_map = loaded_schema.index_validate_template.get(xtype)
        if template_map is None or len(template_map)==0:
            # bug = {
            #     "category": "warn_validate_template",
            #     "description": "no template found",
            #     "class": xtype,
            #     "item": cns_item,
            # }
            # report.report_bug(bug)
            continue


        #validate one by one
        for template in template_map.values():
            _validate_one_template(loaded_schema, types, cns_item, xtype, template, validated_property, report)

    #properties not validate by main template

    all_property = set(cns_item.keys())
    all_property = all_property.difference(get_system_property())
    all_property = all_property.difference(validated_property)
    c = types[0]
    for p in all_property:
        if p.startswith("rdfs:"):
            continue
        #if p in ["in","out"]:
        #    continue

        bug = {
            "category": "warn_validate_template_regular",
            "description": u"unable to find a template for property=[{}] based on classes defined in @type=[{}]".format(p, u", ".join(types)),
            "value": cns_item,
            "class": c,
            "property": p,
        }
        #logging.info(bug)
        report.report_bug(bug)

        # not validated properties for main type
        key_cp = u"ucp_{}_{}".format(c, p)
        report.data[XTEMPLATE][key_cp] += 1


def _validate_one_template(loaded_schema, types, cns_item, xtype, template, validated_property, report):
    p = template["refProperty"]

    # only count main type's  template
    main_type_list = loaded_schema.get_main_types(types)
    for main_type in main_type_list:
        if xtype in main_type_list and xtype != main_type:
            continue

        key_cp = u"cp_{}_{}_{}".format(main_type, xtype, p)
        if p in cns_item:
            report.data[XTEMPLATE][key_cp] += 1
        else:
            report.data[XTEMPLATE][key_cp] += 0

    if p in validated_property:
        # validated, no need to be validated in other templates
        return
    else:
        validated_property.add(p)

    #validate cardinality
    values = json_get_list(cns_item, p)
    card_actual = len(values)
    range_config = template["propertyRange"]


    if len(range_config["python_type_value_list"])>0 or len(range_config["cns_range_datastructure"])>0:
        if card_actual < template["minCardinality"]:
            # logging.info(json4debug(template))
            # logging.info(json4debug(cns_item))
            # assert False
            bug = {
                "category": "warn_validate_template_regular",
                "description": "minCardinality",
                "class": xtype,
                "property": p,
                "expected": template["minCardinality"],
                "actual": card_actual,
                "value": cns_item,
                "item_name": cns_item.get("name"),
                "item_value": cns_item.get(p),
            }
            report.report_bug(bug)


        if "maxCardinality" in template:
            if card_actual > template["maxCardinality"]:
                bug = {
                    "category": "warn_validate_template_regular",
                    "description": "maxCardinality",
                    "class": xtype,
                    "property": p,
                    "value": cns_item,
                    "expected": template["maxCardinality"],
                    "actual": card_actual,
                    "item_name": cns_item.get("name"),
                    "item_value": cns_item.get(p),
                }
                report.report_bug(bug)

    if card_actual == 0:
        # no further validation on range
        return

    #logging.info(template)

    for v in values:
        range_actual = type(v)
        if range_actual in [dict]:
            #CnsDataStructure
            if p in ["in","out"]:
                _validate_entity_ref(xtype, p, v, range_actual, range_config, report)
            elif "@id" in v:
                _validate_entity_ref(xtype, p, v, range_actual, range_config, report)

                v_types = json_get_list(v, "@type")
                if v_types:
                    _validate_template(loaded_schema, v, v_types, report)
            else:
                v_types = _validate_datastructure(xtype, p, v, range_actual, range_config, report)

                if v_types:
                    if len(v_types) == 1:
                        v_types = loaded_schema.index_inheritance["rdfs:subClassOf"].get(v_types[0])

                    _validate_template(loaded_schema, v, v_types, report)

        elif range_actual in [list]:
            assert False #unexpected
        else:
            type_actual = _validate_datatype(xtype, p, v, range_actual, range_config, report)



def _validate_datastructure(c, p, v, range_actual, range_config, report):
    types = range_config["cns_range_datastructure"]
    if len(types) == 0:
        bug = {
            "category": "warn_validate_datastructure",
            "description": "value range not specified as datastructure",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["text"],
            "actual" : None,
        }
        report.report_bug(bug)
    return types

    # xtype = json_get_list(v, "@type")
    # if not xtype:
    #     bug = {
    #         "category": "warn_validate_template_range",
    #         "description": "range value type/datastructure missing",
    #         "value": v,
    #         "class": c,
    #         "property": p,
    #         "expected" : range_config["text"],
    #         "actual" : None,
    #     }
    #     report.report_bug(bug)
    #     return
    #
    # xtype_main = xtype[0]
    # if not xtype_main in range_config["cns_range_datastructure"]:
    #     bug = {
    #         "category": "warn_validate_template_range",
    #         "description": "range value type/datastructure mismatch",
    #         "value": v,
    #         "class": c,
    #         "property": p,
    #         "expected" : range_config["cns_range_datastructure"],
    #         "actual" : xtype,
    #     }
    #     report.report_bug(bug)

def _validate_entity_ref(c, p, v, range_actual, range_config, report):
    xtype = json_get_list(v, "@type")
    if not xtype:
        bug = {
            "category": "warn_validate_entity_ref",
            "description": "value type missing",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["text"],
            "actual" : None,
        }
        report.report_bug(bug)
        return

    xtype_main = xtype[0]
    if range_config["cns_range_entity"] and range_config["cns_range_entity"][0] in xtype:
        pass
    elif xtype_main in range_config["cns_range_entity"]:
        pass
    else:
        bug = {
            "category": "warn_validate_entity_ref",
            "description": "value type/entity mismatch",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["cns_range_entity"],
            "actual" : xtype,
        }
        report.report_bug(bug)

def _validate_datatype(c, p, v, range_actual, range_config, report):

    if p in ["in","out"]:
        # do not validate system property
        return

    if not range_actual in range_config["python_type_value_list"]:
        bug = {
            "category": "warn_validate_datatype",
            "description": "range value datatype mismatch",
            "actualValue": v,
            "class": c,
            "property": p,
            "expected" : range_config["text"],
            "actual" : str(range_actual),
        }
        report.report_bug(bug)


    #logging.info(json4debug(range_config["text"]))
    if range_config["text"].lower() == "date":
        ret = iso8601_date_parse(v)
        if not ret:
            bug = {
                "category": "warn_validate_datatype",
                "description": "range value is valid Date string",
                "actualValue": v,
                "class": c,
                "property": p,
                "expected" : range_config["text"],
                "actual" : str(range_actual),
            }
            report.report_bug(bug)

        #assert False
    elif range_config["text"].lower() == "datetime":
        ret = iso8601_datetime_parse(v)
        if not ret:
            bug = {
                "category": "warn_validate_datatype",
                "description": "range value is valid DateTime string",
                "actualValue": v,
                "class": c,
                "property": p,
                "expected" : range_config["text"],
                "actual" : str(range_actual),
            }
            report.report_bug(bug)
        #assert False

#ISO8601_REGEX_VALIDATE = re.compile(r"^[0-9TZ:\-\.]$")
ISO8601_REGEX_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO8601_REGEX_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
def iso8601_date_parse(datestr):
    if isinstance(datestr, basestring):
        return ISO8601_REGEX_DATE.match(datestr)

def iso8601_datetime_parse(datestr):
    if isinstance(datestr, basestring):
        return ISO8601_REGEX_DATETIME.match(datestr)

#
# def _validate_range(loaded_schema, cns_item, report):
#     #TODO only validate non object range for now
#
#     TEXT_PROP = [""]
#     for p in cns_item:
#         if p in ["@context"]:
#             #skip this range check
#             bug = {
#                 "category": "info_validate_range",
#                 "description": "skip validating range @vocab",
#                 #"item": cns_item
#             }
#             report.report_bug(bug)
#             continue
#
#         rangeExpect = loaded_schema.index_validate_range.get(p)
#         if not rangeExpect:
#             bug = {
#                 "category": "warn_validate_range",
#                 "description": "range not specified in schema",
#                 "property": p
#             }
#             report.report_bug(bug)
#             continue
#
#         for v in json_get_list(cns_item, p):
#             if "python_type_value_list" in rangeExpect:
#                 range_actual = type(v)
#                 if range_actual in rangeExpect["python_type_value_list"]:
#                     # this case is fine
#                     pass
#                 else:
#                     bug = {
#                         "category": "warn_validate_range",
#                         "description": "range value datatype mismatch",
#                         "actualValue": v,
#                         "property": p,
#                         "expected" : rangeExpect["text"],
#                         "actual" : str(range_actual),
#                     }
#                     report.report_bug(bug)
#             else:
#                 if type(v)== dict:
#                     range_actual = v.get("@type",[])
#                     if set(rangeExpect["cns_range_list"]).intersection(range_actual):
#                         # this case is fine
#                         pass
#                     else:
#                         bug = {
#                             "category": "warn_validate_range",
#                             "description": "range object missing types",
#                             "property": p,
#                             "expected" : rangeExpect["cns_range_list"],
#                             "actual" : range_actual,
#                         }
#                         report.report_bug(bug)
#                 else:
#                     bug = {
#                         "category": "warn_validate_range",
#                         "description": "range value should be object",
#                         "property": p,
#                         "expected" : rangeExpect["cns_range_list"],
#                         "actual" : v,
#                         #"item" : v,
#                     }
#                     report.report_bug(bug)
#
#
# def _validate_domain(loaded_schema, cns_item, report):
#     # template validation
#     validated_property = set()
#     for p in cns_item:
#         domainExpected = loaded_schema.index_validate_domain.get(p)
#         if domainExpected == None:
#             bug = {
#                 "category": "warn_validate_domain",
#                 "description": "domain not specified in schema",
#                 "property": p
#             }
#             report.report_bug(bug)
#             continue
#
#
#
#         domainActual = cns_item.get("@type",[])
#         for domain in domainActual:
#             if not loaded_schema.index_definition_alias.get(domain):
#                 bug = {
#                     "category": "warn_validate_definition",
#                     "description": "class not defined in schema",
#                     "class": domain
#                 }
#                 report.report_bug(bug)
#
#         if not domainActual:
#             bug = {
#                 "category": "warn_validate_domain",
#                 "description": "domain not specified",
#                 "property": p,
#                 "item": cns_item
#             }
#             report.report_bug(bug)
#         elif set(domainExpected).intersection(domainActual):
#             # this case is fine
#             pass
#         else:
#             bug = {
#                 "category": "warn_validate_domain",
#                 "description": "domain unexpected",
#                 "actualValue": cns_item[p],
#                 "property": p,
#                 "expected": domainExpected,
#                 "actual": domainActual
#             }
#             report.report_bug(bug)



def task_validate(args):
    logging.info( "called task_validate" )
    schema_filename = args.get("input_schema")
    if not schema_filename:
        schema_filename = "schema/cns_top.jsonld"

    preload_schema_list = preload_schema(args)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(schema_filename, preload_schema_list)


    filepath = args["input_file"]
    filename_list = glob.glob(filepath)
    report = init_report()

    # init xtemplate
    report.data[XTEMPLATE] = collections.Counter()
    for template in loaded_schema.metadata["template"]:
        d = template["refClass"]
        p = template["refProperty"]
        key_cp = u"cp_{}_{}_{}".format(d, d, p)
        report.data[XTEMPLATE][key_cp] += 0
    logging.info(json4debug(report.data[XTEMPLATE]))

    # init class path dependency
    for template in loaded_schema.metadata["template"]:
        d = template["refClass"]
        key_cp = u"parent_{}".format(d)
        report.data[XTEMPLATE][key_cp] = loaded_schema.index_inheritance["rdfs:subClassOf"].get(d)

    for definition in loaded_schema.definition.values():
        if "rdfs:Class" in definition["@type"]:
            d = definition["name"]
            key_cp = u"parent_{}".format(d)
            report.data[XTEMPLATE][key_cp] = loaded_schema.index_inheritance["rdfs:subClassOf"].get(d)

    #validate
    lines = []

    for filename in filename_list:
        logging.info(filename)
        if not os.path.exists(filename):
            continue

        if args.get("option") == "jsons":
            for idx, line in enumerate(file2iter(filename)):
                if idx % 10000 ==0:
                    logging.info(idx)
                    logging.info(json4debug(report))
                json_data = json.loads(line)
                run_validate(loaded_schema, json_data, report)
                stat_kg_report_per_item(json_data, None, report.data["stats"])

                # collection entity listing
                if "CnsLink" not in json_data["@type"]:
                    entity_simple = [
                        json_data["@type"][0],
                        json_data.get("name",""),
                         "\""+u",".join(json_data.get("alternateName",[]))+"\""
                    ]
                    lines.append(u",".join(entity_simple))

        else:
            jsondata = file2json(filename)
            run_validate(loaded_schema, jsondata, report)

    #out
    filename = args["output_validate_entity"]
    logging.info(filename)
    lines = sorted(lines)

    fields = ["main_type","name","alternateName"]
    lines.insert(0, u",".join(fields))
    lines2file(lines, filename)

    #display report
    logging.info(json4debug(report))

    #write report csv
    write_csv_report(args, report, loaded_schema)

    filename = args["output_validate_report"].replace("csv","json")
    logging.info(filename)
    json2file(report, filename)

def write_csv_report(args, report, loaded_schema):
    # generate output report
    lines = []
    fields = ["main_type","super_type","property","main_type_zh","super_type_zh","property_zh","count","coverage"]
    lines.append(u",".join(fields))
    for k, cnt in report.data[XTEMPLATE].items():
        if k.startswith("cp_"):
            if cnt == 0:
                #skip link
                continue

            temp = k.split("_")
            total = report.data[XTEMPLATE]["type_all_{}".format(temp[1])]
            if temp[1].startswith("rdf"):
                nameZh1 = ""
            else:
                nameZh1 = loaded_schema.get_definition_by_alias(temp[1])["nameZh"]
            row = [
                #"main_type":
                temp[1],
                #"super_type":
                temp[2],
                #"property":
                temp[3],
                #"main_type_zh":
                nameZh1,
                #"super_type_zh":
                loaded_schema.get_definition_by_alias(temp[2])["nameZh"],
                #"property_zh":
                loaded_schema.get_definition_by_alias(temp[3])["nameZh"],
                #"count":
                "%d" % cnt,
                #"coverage":
                "%1.2f" % (1.0* cnt/total) if total>0 else "",
            ]

            lines.append(u",".join(row))

    filename = args["output_validate_report"]
    logging.info(filename)
    lines = sorted(lines)
    lines2file(lines, filename)

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--schema_dir': 'input schema',
        '--input_schema': 'input schema',
        '--output_validate_report': 'output validation report',
        '--output_validate_entity': 'output validation entity list',
        '--debug_dir': 'debug directory',
        '--option': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    # task 3: validate
    python kgtool/cns_validate.py task_validate --input_file=schema/cns_top.jsonld --debug_dir=local/debug --schema_dir=schema
    python kgtool/cns_validate.py task_validate --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/debug --schema_dir=schema
    python kgtool/cns_validate.py task_validate --input_file=tests/test_cns_schema_input1.json --debug_dir=local/debug --schema_dir=schema

    python kgtool/cns_validate.py task_validate --input_file=schema/cns_schemaorg.jsonld  --debug_dir=local/debug --schema_dir=schema --output_validate_entity=local/temp/entity.csv --output_validate_report=local/temp/report.csv

    python kgtool/cns_validate.py task_validate --input_file=local/kg4ai_cn_1.0.1.jsondl --input_schema=local/schema/cns_kg4ai.jsonld --debug_dir=local/debug --schema_dir=schema --output_validate_entity=local/temp/entity.csv --output_validate_report=local/temp/report.csv

"""
