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


def run_validate_recursive(loaded_schema, cns_item_list, report, parent_item=None):
    if type(cns_item_list) == list:
        for cns_item in cns_item_list:
            run_validate_recursive(loaded_schema, cns_item, report, parent_item)
    elif type(cns_item_list) == dict:
        run_validate(loaded_schema, cns_item_list, report, parent_item == None)
        next_list = [v for p,v in cns_item_list.items() if p not in ["@context"]]
        run_validate_recursive(loaded_schema, next_list, report, cns_item_list)
    else:
        # do not validate
        pass


def run_validate(loaded_schema, cns_item, report, is_top_level_item):
    """
        validate the following
        * template restriction  (class-property binding)

        * range of property
    """
    report["stats"]["items_validated"] += 1

    if not _validate_system(loaded_schema, cns_item, report):
        return report

    _validate_definition(loaded_schema, cns_item, report)

    _validate_template(loaded_schema, cns_item, report, is_top_level_item)

    #_validate_range(loaded_schema, cns_item, report)

    #_validate_domain(loaded_schema, cns_item, report)

    return report

def _validate_system(loaded_schema, cns_item, report):
    # if "@vocab" in cns_item:
    #     bug = {
    #         "category": "info_validate_system",
    #         "text": "skip validating system @vocab",
    #     }
    #     write_report(report, bug)
    #     return False

    types = json_get_list(cns_item,"@type")
    if not types:
        bug = {
            "category": "warn_validate_system",
            "text": "item missing @type",
            "item": cns_item
        }
        write_report(report, bug)
        return False

    if not isinstance(cns_item["@type"], list):
        bug = {
            "category": "warn_validate_system",
            "text": "item @type is not a list",
            "item": cns_item
        }
        write_report(report, bug)
        #return False

    if "Thing" in types:
        if not "@id" in cns_item:
            bug = {
                "category": "warn_validate_system",
                "text": "instance of [Thing] missing @id",
                "item": cns_item
            }
            write_report(report, bug)
            return False


    return True


def _validate_definition(loaded_schema, cns_item, report):
    """
        if @type and all properties are defined in schema
    """
    #types
    for xtype in json_get_list(cns_item,"@type"):
        has_definition = False
        for schema in loaded_schema.loaded_schema_list:
            the_definition = schema.get_definition_by_alias(xtype)
            if the_definition:
                has_definition =True
                break

        if not has_definition:
            bug = {
                "category": "info_validate_definition",
                "text": "class not defined",
                "class" : xtype,
                #"item": cns_item
            }
            write_report(report, bug)

    for property in cns_item:
        if property in get_system_property():
            continue

        has_definition = False
        for schema in loaded_schema.loaded_schema_list:
            the_definition = schema.get_definition_by_alias(property)
            if the_definition:
                has_definition =True
                break

        if not has_definition:
            bug = {
                "category": "info_validate_definition",
                "text": "property not defined",
                "property" : property,
                #"item": cns_item
            }
            write_report(report, bug)

def get_system_property():
    return ["@context","@vocab", "@graph", "@id", "@type"]


def _validate_template(loaded_schema, cns_item, report, is_top_level_item):
    # template validation
    xtemplate = "xtemplate"
    if xtemplate not in report:
        report[xtemplate] = collections.Counter()


    validated_property = set()

    _count_links(cns_item, report,xtemplate)

    if _validate_template_special(loaded_schema, cns_item, report,xtemplate,validated_property):
        return
    _validate_template_regular(loaded_schema, cns_item, report, xtemplate, validated_property, is_top_level_item)


def _count_links(cns_item, report, xtemplate):
    types = json_get_list(cns_item,"@type")
    if "CnsLink" in types:
        main_type_in = cns_item["in"]["@type"][0]
        main_type_out = cns_item["out"]["@type"][0]

        key_cnslink = u"cnslink_total"
        report[xtemplate][key_cnslink] += 1

        key_cnslink = u"cnslink_{}_{}_{}".format(main_type_in, types[0], main_type_out)
        report[xtemplate][key_cnslink] += 1


def _validate_template_special(loaded_schema, cns_item, report, xtemplate, validated_property):
    #special case
    types = json_get_list(cns_item,"@type")
    if "CnsLink" in types and re.search(r"^[a-z]", types[0]):
        types_domain = json_get_list(cns_item["in"], "@type")
        for xtype in types_domain:
            template_list = loaded_schema.index_validate_template.get(xtype)
            if template_list is None or len(template_list)==0:
                continue

            for template in template_list:
                p = template["refProperty"]
                if types[0] != p:
                    continue

                v = cns_item["out"]
                range_actual = type(v)
                range_config = template["propertyRange"]
                type_actual = _validate_entity(xtype, p, v, range_actual, range_config, report)
                validated_property.add(p)
                return True


def _validate_template_regular(loaded_schema, cns_item, report, xtemplate, validated_property, is_top_level_item):
    #regular validation
    types = json_get_list(cns_item,"@type")
    main_type = types[0]
    for idx, xtype in enumerate(types):
        # only count main type's  template
        if idx == 0:
            if is_top_level_item:
                key_c = u"type_{}".format(xtype)
                report[xtemplate][key_c] += 1


        #find templates
        template_list = loaded_schema.index_validate_template.get(xtype)
        if template_list is None or len(template_list)==0:
            # bug = {
            #     "category": "warn_validate_template",
            #     "text": "no template found",
            #     "class": xtype,
            #     "item": cns_item,
            # }
            # write_report(report, bug)
            continue


        #validate one by one
        for template in template_list:
            p = template["refProperty"]

            # only count main type's  template
            if is_top_level_item:
                key_cp = u"cp_{}_{}_{}".format(main_type, xtype, p)
                if p in cns_item:
                    report[xtemplate][key_cp] += 1
                else:
                    report[xtemplate][key_cp] += 0

            if p in validated_property:
                # validated, no need to be validated in other templates
                continue
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
                        "category": "warn_validate_template",
                        "text": "minCardinality",
                        "class": xtype,
                        "property": p,
                        "expected": template["minCardinality"],
                        "actual": card_actual,
                        "item_name": cns_item.get("name"),
                        "item_value": cns_item.get(p),
                    }
                    write_report(report, bug)


                if "maxCardinality" in template:
                    if card_actual > template["maxCardinality"]:
                        bug = {
                            "category": "warn_validate_template",
                            "text": "maxCardinality",
                            "class": xtype,
                            "property": p,
                            "expected": template["maxCardinality"],
                            "actual": card_actual,
                            "item_name": cns_item.get("name"),
                            "item_value": cns_item.get(p),
                        }
                        write_report(report, bug)

            if card_actual == 0:
                # no further validation on range
                continue

            #logging.info(template)

            for v in values:
                range_actual = type(v)
                if range_actual in [dict]:
                    #CnsDataStructure
                    if p in ["in","out"]:
                        type_actual = _validate_entity(xtype, p, v, range_actual, range_config, report)
                    elif "@id" in v:
                        type_actual = _validate_entity(xtype, p, v, range_actual, range_config, report)
                    else:
                        type_actual = _validate_datastructure(xtype, p, v, range_actual, range_config, report)
                elif range_actual in [list]:
                    assert False #unexpected
                else:
                    type_actual = _validate_datatype(xtype, p, v, range_actual, range_config, report)

    #properties not validate by main template
    all_property = set(cns_item.keys())
    all_property = all_property.difference(get_system_property())
    all_property = all_property.difference(validated_property)
    c = types[0]
    for p in all_property:
        if p.startswith("rdfs:"):
            continue

        bug = {
            "category": "warn_validate_template_range",
            "text": "property not validated by main template",
            "value": cns_item,
            "class": c,
            "property": p,
        }
        write_report(report, bug)

        # not validated properties for main type
        key_cp = u"ucp_{}_{}".format(c, p)
        report[xtemplate][key_cp] += 1


def _validate_datastructure(c, p, v, range_actual, range_config, report):
    xtype = json_get_list(v, "@type")
    if not xtype:
        bug = {
            "category": "warn_validate_template_range",
            "text": "range value type/datastructure missing",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["text"],
            "actual" : None,
        }
        write_report(report, bug)
        return

    xtype_main = xtype[0]
    if not xtype_main in range_config["cns_range_datastructure"]:
        bug = {
            "category": "warn_validate_template_range",
            "text": "range value type/datastructure mismatch",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["cns_range_datastructure"],
            "actual" : xtype,
        }
        write_report(report, bug)

def _validate_entity(c, p, v, range_actual, range_config, report):
    xtype = json_get_list(v, "@type")
    if not xtype:
        bug = {
            "category": "warn_validate_template_range",
            "text": "range value type missing",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["text"],
            "actual" : None,
        }
        write_report(report, bug)
        return

    xtype_main = xtype[0]
    if range_config["cns_range_entity"] and range_config["cns_range_entity"][0] in xtype:
        pass
    elif  xtype_main in range_config["cns_range_entity"]:
        pass
    else:
        bug = {
            "category": "warn_validate_template_range",
            "text": "range value type/entity mismatch",
            "value": v,
            "class": c,
            "property": p,
            "expected" : range_config["cns_range_entity"],
            "actual" : xtype,
        }
        write_report(report, bug)

def _validate_datatype(c, p, v, range_actual, range_config, report):
    if not range_actual in range_config["python_type_value_list"]:
        bug = {
            "category": "warn_validate_range",
            "text": "range value datatype mismatch",
            "actualValue": v,
            "class": c,
            "property": p,
            "expected" : range_config["text"],
            "actual" : str(range_actual),
        }
        write_report(report, bug)


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
#                 "text": "skip validating range @vocab",
#                 #"item": cns_item
#             }
#             write_report(report, bug)
#             continue
#
#         rangeExpect = loaded_schema.index_validate_range.get(p)
#         if not rangeExpect:
#             bug = {
#                 "category": "warn_validate_range",
#                 "text": "range not specified in schema",
#                 "property": p
#             }
#             write_report(report, bug)
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
#                         "text": "range value datatype mismatch",
#                         "actualValue": v,
#                         "property": p,
#                         "expected" : rangeExpect["text"],
#                         "actual" : str(range_actual),
#                     }
#                     write_report(report, bug)
#             else:
#                 if type(v)== dict:
#                     range_actual = v.get("@type",[])
#                     if set(rangeExpect["cns_range_list"]).intersection(range_actual):
#                         # this case is fine
#                         pass
#                     else:
#                         bug = {
#                             "category": "warn_validate_range",
#                             "text": "range object missing types",
#                             "property": p,
#                             "expected" : rangeExpect["cns_range_list"],
#                             "actual" : range_actual,
#                         }
#                         write_report(report, bug)
#                 else:
#                     bug = {
#                         "category": "warn_validate_range",
#                         "text": "range value should be object",
#                         "property": p,
#                         "expected" : rangeExpect["cns_range_list"],
#                         "actual" : v,
#                         #"item" : v,
#                     }
#                     write_report(report, bug)
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
#                 "text": "domain not specified in schema",
#                 "property": p
#             }
#             write_report(report, bug)
#             continue
#
#
#
#         domainActual = cns_item.get("@type",[])
#         for domain in domainActual:
#             if not loaded_schema.index_definition_alias.get(domain):
#                 bug = {
#                     "category": "warn_validate_definition",
#                     "text": "class not defined in schema",
#                     "class": domain
#                 }
#                 write_report(report, bug)
#
#         if not domainActual:
#             bug = {
#                 "category": "warn_validate_domain",
#                 "text": "domain not specified",
#                 "property": p,
#                 "item": cns_item
#             }
#             write_report(report, bug)
#         elif set(domainExpected).intersection(domainActual):
#             # this case is fine
#             pass
#         else:
#             bug = {
#                 "category": "warn_validate_domain",
#                 "text": "domain unexpected",
#                 "actualValue": cns_item[p],
#                 "property": p,
#                 "expected": domainExpected,
#                 "actual": domainActual
#             }
#             write_report(report, bug)



def task_validate(args):
    logging.info( "called task_validate" )
    schema_filename = args.get("input_schema")
    if not schema_filename:
        schema_filename = "schema/cns_top.jsonld"

    preloadSchemaList = preload_schema(args)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(schema_filename, preloadSchemaList)


    filepath = args["input_file"]
    filename_list = glob.glob(filepath)
    report = init_report()

    # init xtemplate
    xtemplate = "xtemplate"
    report[xtemplate] = collections.Counter()
    for template in loaded_schema.metadata["template"]:
        d = template["refClass"]
        p = template["refProperty"]
        key_cp = u"cp_{}_{}_{}".format(d, d, p)
        report[xtemplate][key_cp] += 0
    logging.info(json4debug(report[xtemplate]))

    # init class path dependency
    for template in loaded_schema.metadata["template"]:
        d = template["refClass"]
        key_cp = u"parent_{}".format(d)
        report[xtemplate][key_cp] = loaded_schema.index_inheritance["rdfs:subClassOf"].get(d)

    for definition in loaded_schema.definition.values():
        if "rdfs:Class" in definition["@type"]:
            d = definition["name"]
            key_cp = u"parent_{}".format(d)
            report[xtemplate][key_cp] = loaded_schema.index_inheritance["rdfs:subClassOf"].get(d)

    #validate
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
                run_validate_recursive(loaded_schema, json_data, report)
                stat_kg_report_per_item(json_data, None, report["stats"])

        else:
            jsondata = file2json(filename)
            run_validate_recursive(loaded_schema, jsondata, report)

    #display report
    logging.info(json4debug(report))

    #write report csv
    write_csv_report(args, report, loaded_schema, xtemplate)

def write_csv_report(args, report, loaded_schema, xtemplate):
    # generate output report
    lines = []
    fields = ["main_type","super_type","property","main_type_zh","super_type_zh","property_zh","count","coverage"]
    lines.append(u",".join(fields))
    for k, cnt in report[xtemplate].items():
        if k.startswith("cp_"):
            temp = k.split("_")
            total = report[xtemplate]["type_{}".format(temp[1])]
            row = [
                #"main_type":
                temp[1],
                #"super_type":
                temp[2],
                #"property":
                temp[3],
                #"main_type_zh":
                loaded_schema.get_definition_by_alias(temp[1])["nameZh"],
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

    filename = args["output_file"]
    logging.info(filename)
    lines2file(lines, filename)

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--dir_schema': 'input schema',
        '--input_schema': 'input schema',
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

    python kgtool/cns_validate.py task_validate --input_file=local/kg4ai_cn_1.0.1.jsondl --input_schema=local/schema/cns_kg4ai.jsonld --debug_dir=local/debug --dir_schema=schema

"""
