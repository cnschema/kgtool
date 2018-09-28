#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Li Ding

from __future__ import unicode_literals
from __future__ import print_function

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

from cns_model import CnsSchema
from cns_validate import run_validate_recursive
from core import parse_list_value, is_empty_string


# global constants
VERSION = 'v20180919'
CONTEXTS = [os.path.basename(__file__), VERSION]

"""
a table representation of cnSchema consists of four tables
* definition  (CnsDefinition)
* template (CnsTemplate)
* changelog (CnsChangelog)
* metadata  (CnsOntologyRelease)


"""
CNS_SCHEMA_SHEET = [{
        "config":{
            "non_empty_columns": ["property", "value"],
            "type_predefined": ["CnsOntologyRelease", "CnsMeta"],
            "id_pattern": "http://meta.cnschema.org/schema/{name}/{version}"
        },
        "sheetname": "metadata",
        "rows": [],
        "columns": [
            "version",
            "property",
            "value"
        ]
    }, {
        "config":{
            "non_empty_columns": ["name", "nameZh", "category"],
            "type_predefined": ["CnsDefinition", "CnsMeta"],
            "name_pattern": "{name}",
            "id_pattern": "http://cnschema.org/{name}"
        },
    	"sheetname": "definition",
    	"rows": [],
    	"columns": [
    		"version",
    		"category",
    		"name",
    		"super",
    		"supersededBy",
    		"schemaorgName",
    		"wikidataName",
    		"wikipediaName",
    		"cnschemaName",
    		"nameZh",
    		"alternateName",
    		"descriptionZh",
    		"descriptionZhSource",
    		"description",
    		"descriptionSource",
    		"range"
    	]
    }, {
        "config":{
            "non_empty_columns": ["refClass", "refProperty"],
            "type_predefined": ["CnsTemplate", "CnsMeta"],
            "name_pattern": "{refClass}_{refProperty}",
            "id_pattern": "http://meta.cnschema.org/template/{refClass}_{refProperty}"
        },
    	"sheetname": "template",
    	"rows": [],
    	"columns": [
    		"version",
    		#"category",
    		"minCardinality",
    		"maxCardinality",
    		"keywords",
    		"refClass",
    		"refProperty",
    		"propertyRange",
    		"propertySchema",
    		"templateGroup",
    		"propertyNameZh",
    		"propertyAlternateName",
    		"propertyDescription",
    		"propertyDescriptionSource",
    		"propertyDescriptionZh",
    		"propertyDescriptionZhSource",
    		"exampleValueText",
    		#"exampleValue",
    		"exampleValueJson"
    	]
    }, {
        "config":{
            "non_empty_columns": ["name", "datePublished", "description"],
            "type_predefined": ["CnsChangelog", "CnsMeta"],
            "name_pattern": "{name}",
            "id_pattern": "http://meta.cnschema.org/changelog/{name}"
        },
    	"sheetname": "changelog",
    	"rows": [],
    	"columns": [
    		"version",
    		"name",
    		"datePublished",
    		"description",
    		"changeOperation",
    		"changeSheet",
    		"changeRow",
    		"changeColumn",
    		"contentBefore",
    		"contentAfter"
    	]
    }]

CNS_SCHEMA_SHEET_INDEX = dict([[x["sheetname"], x] for x in CNS_SCHEMA_SHEET ])



def _is_valid_row(item):
    # all valid definition has version number starting with "v"
    version = item["version"]
    if is_empty_string(version):
        return False

    if not isinstance(version, basestring):
        return False

    if not version.startswith("v"):
        return False

    return True

def _excel2jsonld_item(cns_item, item):

    #logging.info(json4debug(item))

    #definition
    if "category" in item:
        if item["category"] in ["class", "datatype", "struct", "meta"]:
            #cns_item["@type"].insert(0,  "rdfs:Class")
            cns_item["@type"].insert(0,  "CnsClass")
        elif item["category"] in [ "link", "property"]:
            #cns_item["@type"].insert(0,  "rdf:Property")
            cns_item["@type"].insert(0,  "CnsProperty")
        else:
            logging.info(item["category"])
            assert False

    for p, v in item.items():
        # rewrite
        assert v != None

        if p =="" or v == None or v == "" or v == None:
            continue

        #definition
        elif p  == "super":
            if "CnsProperty" in cns_item["@type"]:
                px = "rdfs:subPropertyOf"
            elif "CnsClass" in cns_item["@type"]:
                px = "rdfs:subClassOf"
            else:
                logging.info(json4debug(cns_item["@type"]))
                assert False
            cns_item[px] =  parse_list_value(v)
        elif p  == "domain":
            px = "rdfs:domain"
            cns_item[px] = parse_list_value(v)
#        elif p  == "range":
#            px = "rdfs:range"
#            cns_item[px] =  v
        elif p == "supersededBy":
            pass
        elif p == "schemaorgName":
            px = "schemaorgUrl"
            cns_item[px] = "http://schema.org/{}".format( v )
        elif p == "wikipediaName":
            px = "wikipediaUrl"
            cns_item[px] = "https://en.wikipedia.org/wiki/{}".format( v )
        elif p == "wikidataName":
            px = "wikidataUrl"
            cns_item[px] = "https://www.wikidata.org/wiki/{}".format( v )
        elif p == "cnschemaName":
            pass

        #copy
        elif p in ["alternateName", "propertyAlternateName", "keywords"]:
            vx = parse_list_value(v)
            if vx:
                cns_item[p] = vx
        else:
            cns_item[p] = v
    return cns_item

def _jsonld2excel_item(cns_item):
    ret = {}

    for p,v in cns_item.items():
        assert v != None
        if p in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
            px = "super"
            ret[px] = v
#        elif p == "rdfs:range":
#            px = "range"
#            ret[px] = v
        elif p == "schemaorgUrl":
            px = "schemaorgName"
            cns_item[px] = v.replace("http://schema.org/","")
        elif p == "wikipediaName":
            px = "wikipediaUrl"
            cns_item[px] = v.replace("https://en.wikipedia.org/","")
        elif p == "wikidataUrl":
            px = "wikidataName"
            cns_item[px] = v.replace("https://www.wikidata.org/wiki/","")

        elif p.startswith("@"):
            pass
        else:
            ret[p] = v

    return _clean_list_value(ret)


def _clean_list_value(cns_item):
    cns_item_out = {}
    for k,v in cns_item.items():
        if k in ["@id", "@type"]:
            continue

        if isinstance(v, list):
            cns_item_out[k] = u", ".join(v)
        elif isinstance(v, dict):
            assert False
        else:
            cns_item_out[k] = v
    return cns_item_out



def mem2table(the_schema, flag_import):
    if flag_import:
        schema_list = the_schema.imported_schema
    else:
        schema_list = [the_schema]

    output_rows = collections.defaultdict(list)
    for schema in schema_list:
        # definition , template, changelog
        map_name_sheet = {
            "definition": sorted(schema.definition.values(), key=lambda x:x["name"]),
            "template": schema.metadata["template"],
            "changelog": schema.metadata["changelog"],
        }

        for sheetname, table in map_name_sheet.items():
            for cns_item in table:
                #logging.info(cns_item)

                if flag_import:
                    cns_item["statedIn"] = schema.metadata["name"]

                if "definition" == sheetname:
                    cns_item["cnschemaName"] = cns_item["name"]

                cns_item = _jsonld2excel_item(cns_item)

                output_rows[sheetname].append(cns_item)

        # metadata
        sheetname = "metadata"
        for p, v in schema.metadata.items():
            if p in ["template", "changelog"]:
                continue
            if p.startswith("@"):
                continue

            if isinstance(v, dict):
                if p in ["about"]:
                    continue
                else:
                    logging.info(p)
                    logging.info(v)
                    assert False

            cns_item ={
                "version": schema.metadata["version"],
                "property":p,
                "value":v,
            }
            if flag_import:
                cns_item["statedIn"] = schema.metadata["name"]

            output_rows[sheetname].append(cns_item)

    #logging.info(json4debug(output_rows))
    #assert False
    dataTable2018 = []
    for schema_sheet  in CNS_SCHEMA_SHEET:
        sheetname = schema_sheet["sheetname"]
        columns = []
        columns.extend(schema_sheet["columns"])
        columns.append("statedIn")
        sheet = {
            "sheetname": sheetname,
            "columns": columns,
            "rows": output_rows[sheetname],
        }
        dataTable2018.append(sheet)

    return dataTable2018


class CnsModelTable():
    def __init__(self):
        #cnSchema存储
        self.schema = CnsSchema()
        self.report = self.schema.report


    def table2mem(self, excel_data, preloaded_schema_list=None):
        #logging.info(json4debug(excel_data))
        self._run_validate_excel_data(excel_data)
        if self.report.has_bug():
            return False

        self._run_load_excel_data(excel_data)
        if self.report.has_bug():
            return False

        self.schema.build( preloaded_schema_list )
        if self.report.has_bug():
            return False

        #validate4jsonld
        json_data = self.schema.mem2jsonld()
        run_validate_recursive(self.schema, json_data, self.report)
        if self.report.has_bug():
            return False

        return self.schema

    def _run_load_excel_data(self, excel_data):

        excel_data_index = dict([[x["sheetname"], x] for x in excel_data ])
        for schema_sheet in CNS_SCHEMA_SHEET:
            sheet_name = schema_sheet["sheetname"]
            sheet = excel_data_index.get(sheet_name)
            if not schema_sheet:
                continue

            #process rows
            visited_name = set()
            for row_index, row in enumerate(sheet["rows"]):
                if not self._validate_one_row(row, row_index,  sheet_name, schema_sheet):
                    continue

                cns_item = self._convert_one_row(row, schema_sheet)

                #check for duplicated name
                if  cns_item is None:
                    pass
                elif cns_item["name"] in visited_name:
                    bug ={
                        "category": "error_excel_row_duplicated_name",
                        "description": "duplicated name sheet={}, row={}, name={}".format(sheet_name, row_index-1, cns_item["name"]),
                    }
                    self.report.report_bug(bug)
                else:
                    visited_name.add(cns_item["name"])



    def _convert_one_row(self, row, schema_sheet):
        sheet_name = schema_sheet["sheetname"]

        if sheet_name == "metadata":
            self.schema.add_metadata( row["property"], row["value"] )
            return None

        #logging.info(json4debug(row))
        cns_item = {
            "@id":  schema_sheet["config"]["id_pattern"].format(**row),
            "@type":  copy.deepcopy(schema_sheet["config"]["type_predefined"]),
            "name": schema_sheet["config"]["name_pattern"].format(**row)
        }

        cns_item  = _excel2jsonld_item(cns_item, row)

        if sheet_name == "definition":
            self.schema.set_definition( cns_item )
        elif sheet_name == "template":
            self.schema.add_metadata( sheet_name, cns_item )
        elif sheet_name == "changelog":
            self.schema.add_metadata( sheet_name, cns_item )
        else:
            assert False
        return cns_item

    def _run_validate_excel_data(self, excel_data):
        excel_data_index = dict([[x["sheetname"], x] for x in excel_data ])
        cns_index = dict([[x["sheetname"], x] for x in CNS_SCHEMA_SHEET ])

        #check extra sheets
        sheet_name_diff =  set(excel_data_index) - set(CNS_SCHEMA_SHEET_INDEX)
        if sheet_name_diff:
            bug = {
                "keywords":["info", "table2mem"],
                "category": "info_excel_sheet_skip_unsupport",
                "description": "process excel, skip unsupported sheets [{}]".format(", ".join(sheet_name_diff)),
            }
            self.report.report_bug(bug)

        #check missing sheets
        sheet_name_diff =  set(CNS_SCHEMA_SHEET_INDEX) - set(excel_data_index)
        if sheet_name_diff:
            bug = {
                "keywords":["error", "table2mem"],
                "category": "error_excel_sheet_missing",
                "description": "process excel, found missing sheets [{}]".format(", ".join(sheet_name_diff)),
            }
            self.report.report_bug(bug)

        #validate sheet header
        for sheet in excel_data:
            sheet_name = sheet["sheetname"]
            schema_sheet = CNS_SCHEMA_SHEET_INDEX.get(sheet_name)
            if not schema_sheet:
                continue

            self._validate_one_sheet(sheet_name, sheet, schema_sheet)


    def _validate_one_sheet(self, sheet_name, sheet, schema_sheet):

        #validate sheet column
        header_diff = set(schema_sheet["columns"]) - set(sheet["columns"])
        if  header_diff:
            bug = {
                "category": "warn_excel_column_missing",
                u"description": "excel (sheet={}) missing columns [{}]".format(
                    sheet_name,
                    u",".join((header_diff)))
            }
            self.report.report_bug(bug)

    def _validate_one_row(self, row, row_index, sheet_name, schema_sheet):
        ret = True
        #logging.info(idx)
        if not _is_valid_row(row):
            #just skip, no need to report error
            return False

        for p in schema_sheet["config"]["non_empty_columns"]:
            if is_empty_string(row.get(p)):
                bug = {
                    "category": "error_excel_cell_empty_value",
                    u"description": "excel cell expect non-empty value. sheet={} row={} column={}, found empty value".format(sheet_name, row_index, p),
                    "value": row,
                }
                self.report.report_bug(bug)
                ret = False

        return ret
