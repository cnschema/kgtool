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
from kgtool.table import excel2json, json2excel,json2excel4multiple  # noqa
from kgtool.cns_model import CnsSchema, init_report
from kgtool.cns_validate import run_validate_recursive


# global constants
VERSION = 'v20180519'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
* load CnSchema instance
* dump in json for version checking
* generate information quality report
* draw schema diagram
* maintain property mapping

"""

MAP_NAME_URLPATTERN = {
    "schemaorgName": "http://schema.org/{}",
    "wikipediaName": "https://en.wikipedia.org/wiki/{}",
    "wikidataName": "https://www.wikidata.org/wiki/{}"
}

SCHEMA_EXCEL_HEADER = {
	"class": {
		"COPY": [
            "name",
            "nameZh",
            "version",
            "category",
			"descriptionZh",
			"descriptionZhSource",
			"description",
			"descriptionSource"
		],
		"SKIP": ["cnschemaName"]
	},
	"property": {
		"COPY": [
            "name",
			"nameZh",
            "version",
            "category",
			"descriptionZh",
			"descriptionZhSource",
			"description",
			"descriptionSource"
		],
		"SKIP": ["cnschemaName"]
	},
	"template": {
		"COPY": [
            "version",
            "minCardinality",
            "maxCardinality",
            "refClass",
            "refProperty",
            "propertyNameZh",
            "propertyAlternateName",
            "propertyRange",
            "propertySchema",
            "propertyDefinition",
            "propertyDefinitionSource",
            "propertyDefinitionZh",
            "propertyDefinitionZhSource"],
		"SKIP": []
	},
	"changelog": {
		"COPY": ["version", "datePublished", "name", "text"],
		"SKIP": []
	},
	"metadata": {
		"COPY": ["version", "proeprty", "value"],
		"SKIP": []
	}
}

SCHEMA_EXCEL_HEADER_SKIP = {
    "class": [  "cnschemaName",
             ],
    "property": [
                "cnschemaName",
                ],
    "template": [],
    "changelog": [],
}


def init_cns_excel():
    list_sheet_name = []
    map_data_table = {}

    sheetname = "class"
    list_sheet_name.append(sheetname)
    map_data_table[sheetname] = {
        "sheetname": sheetname,
        "rows":[],
        "columns": [ "version",
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
            ]
    }

    sheetname = "property"
    list_sheet_name.append(sheetname)
    map_data_table[sheetname] = {
        "sheetname": sheetname,
        "rows":[],
        "columns": ["version",
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
            "domain",
            "range"
            ]
    }


    sheetname = "template"
    list_sheet_name.append(sheetname)
    map_data_table[sheetname] = {
        "sheetname": sheetname,
        "rows":[],
        "columns":[
            "version",
            "category",
            "minCardinality",
            "maxCardinality",
            "refClass",
            "refProperty",
            "propertyNameZh",
            "propertyAlternateName",
            "propertyRange",
            "propertySchema",
            "propertyDefinition",
            "propertyDefinitionSource",
            "propertyDefinitionZh",
            "propertyDefinitionZhSource"
        ]
    }

    sheetname = "changelog"
    list_sheet_name.append(sheetname)
    map_data_table[sheetname] = {
        "sheetname": sheetname,
        "rows":[],
        "columns":[
            "version",
            "name",
            "datePublished",
            "text"
        ]
    }

    sheetname = "metadata"
    list_sheet_name.append(sheetname)
    map_data_table[sheetname] = {
        "sheetname": sheetname,
        "rows":[],
        "columns":[
            "version",
            "property",
            "value"
        ]
    }

    return list_sheet_name, map_data_table


class CnsExcel():
    def __init__(self):
        #系统处理报告
        self.report = collections.defaultdict(list)

        #cnSchema存储
        self.schema = CnsSchema()


    def load_excel_schema(self, filename):
        excel_data = excel2json(filename)
        name = os.path.basename(filename).split(".")[0]
        self.schema.add_metadata("name", name)

        for sheet_name, items in excel_data["data"].items():
            if self._load_sheet_definition(sheet_name, items, "class"):
                pass
            elif self._load_sheet_definition(sheet_name, items, "property"):
                pass
            elif self._load_sheet_cardinality(sheet_name, items):
                pass
            elif self._load_sheet_changlog(sheet_name, items):
                pass
            elif self._load_sheet_metadata(sheet_name, items):
                pass
            else:
                msg = u"skip sheet {}".format( sheet_name)
                self.report["info"].append(msg)
                logging.info( msg )

        self.schema.build()

    def _is_valid_row(self, item):
        # all valid definition has version number starting with "v"
        if not item[u"version"].startswith("v"):
            return False

        return True


    def _load_sheet_metadata(self,  sheet_name, items):
        xlabel = "metadata"

        if sheet_name == xlabel:
            pass
        else:
            return False

        cns_item_list = []
        for item in items:
            if not self._is_valid_row(item):
                continue

            property = item["property"]
            value = item["value"]
            assert property
            assert value

            self.schema.add_metadata( property, value )

        return True

    def _load_sheet_changlog(self,  sheet_name, items):
        xlabel = "changelog"
        if sheet_name == xlabel:
            xtype = ["CnsChangelog", "CnsMetadata", "Thing"]
        else:
            return False


        cns_item_list = []
        for item in items:
            if not self._is_valid_row(item):
                continue

            name = item["name"]
            assert name
            xid = "http://meta.cnschema.org/changelog/{}".format(name)

            cns_item = {
                "@type": xtype,
                "@id": xid,
                "name": name,
            }
            for p,v in item.items():
                self._copy_values(cns_item, p, v, sheet_name)

            self.schema.add_metadata( xlabel, cns_item )

        return True

    def _cardinality2definition(self, cns_item):
        if cns_item["propertySchema"] == "":
            name = cns_item["refProperty"]
            xid = "http://cnschema.org/{}".format(name)

            cns_item_definition = {
                "@id": xid,
                "@type": ["rdf:Property", "CnsDefinition","CnsMetadata", "Thing"],
                "name": name,
                "category": "property-template",
                "nameZh": cns_item["propertyNameZh"],
                "alternateName": parse_list_value(cns_item["propertyAlternateName"]),
                "rdfs:domain": parse_list_value(cns_item["refClass"]),
                "rdfs:range": cns_item["propertyRange"],
            }
            cns_item_definition_old = self.schema.get_definition(xid)
            if cns_item_definition_old:
                cns_item_definition["rdfs:domain"].extend( cns_item_definition_old["rdfs:domain"] )
                #cns_item_definition["rdfs:range"].extend( cns_item_definition_old["rdfs:range"] )

            self.schema.set_definition( cns_item_definition )

    def _load_sheet_cardinality(self,  sheet_name, items):
        xlabel = "template"
        if sheet_name == xlabel:
            xtype = ["CnsTemplate", "CnsMetadata", "Thing"]
        else:
            return False

        for item in items:
            if not self._is_valid_row(item):
                continue

            name = "{}_{}".format(
                item["refClass"],
                item["refProperty"]
            )

            xid = "http://meta.cnschema.org/template/{}".format( name )
            cns_item = {
                "@type": xtype,
                "@id": xid,
                "name": name
            }
            for p,v in item.items():
                self._copy_values(cns_item, p, v, sheet_name)

            self.schema.add_metadata( "template", cns_item )

            self._cardinality2definition(cns_item)

        return True

    def _copy_values(self, cns_item, p, v, sheet_name):
        if p in SCHEMA_EXCEL_HEADER[sheet_name]["COPY"]:
            cns_item[p] = v
        elif p in SCHEMA_EXCEL_HEADER[sheet_name]["SKIP"]:
            pass
        elif p == "":
            pass
        else:
            msg = u"warn: column {} not in COPY/SKIP in sheet {}".format( p, sheet_name)
            self.report["warn"].append(msg)
            #logging.warn( msg )
            #logging.warn( json4debug( cns_item ) )

    def _load_sheet_definition(self, sheet_name, items, xlabel ):
        if not sheet_name == xlabel:
            return False
        #logging.info( xlabel )

        if "class" == xlabel:
            xtype = ["rdfs:Class", "CnsDefinition", "CnsMetadata", "Thing"]
        elif "property" == xlabel:
            xtype = ["rdf:Property", "CnsDefinition","CnsMetadata", "Thing"]
        else:
            assert False

        for item in items:
            if not self._is_valid_row(item):
                continue

            name = item["name"]
            assert name
            xid = "http://cnschema.org/{}".format(name)

            cns_item = {
                "@type": xtype,
                "@id": xid,
                "name": name,
            }
            for p,v in item.items():
                self._convert_definition(p, v, cns_item, sheet_name)

            self.schema.set_definition( cns_item )

        return True

    def _convert_definition(self, p, v, cns_item, sheet_name):
        if not v:
            return

        if p  == "super":
            if sheet_name == "class":
                px = "rdfs:subClassOf"
            elif sheet_name == "property":
                px = "rdfs:subPropertyOf"
            else:
                assert False
            cns_item[px] =  parse_list_value(v)
        elif p  == "domain":
            px = "rdfs:domain"
            cns_item[px] = parse_list_value(v)
        elif p  == "range":
            px = "rdfs:range"
            cns_item[px] =  v
        elif p == "supersededBy":
            pass
        elif p in MAP_NAME_URLPATTERN:
            px = re.sub("Name", "Url", p)
            cns_item[px] = MAP_NAME_URLPATTERN[p].format( v )
        elif p in ["alternateName"]:
            cns_item[p] =  parse_list_value(v)
        else:
            self._copy_values(cns_item, p, v, sheet_name)

def task_excel2jsonld(args):
    logging.info( "called task_excel2jsonld" )
    obj_excel = CnsExcel()
    filename = args["input_file"]
    obj_excel.load_excel_schema(filename)
    if len(obj_excel.report["warn"])>0:
        logging.info(json4debug(obj_excel.report["warn"]))
        assert False

    filename_output = args["output_file"]
    obj_excel.schema.export_jsonld(filename_output)

    jsondata = file2json(filename_output)
    report = init_report()
    run_validate_recursive(obj_excel.schema, jsondata, report)
    if len(report["bugs"])>2:
        logging.info(json4debug(report))
        assert False
    _export_nquad(args, filename_output)

    _export_excel(args, obj_excel.schema)
    _export_excel(args, obj_excel.schema, flag_import=False)

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

def _export_excel(args, the_schema, flag_import=True):
    xdebug_file = os.path.join(args["debug_dir"],os.path.basename(args["output_file"]))
    xdebug_file = xdebug_file.replace(".jsonld","")

    if flag_import:
        filename_excel = xdebug_file+u".import.xls"
        schema_list = the_schema.loaded_schema_list
    else:
        filename_excel = xdebug_file+u".clean.xls"
        schema_list = [the_schema]

    output_rows = collections.defaultdict(list)
    output_columns = collections.defaultdict(set)

    #init ref
    map_src_property = {}
    for schema in the_schema.loaded_schema_list:
        for name in sorted(schema.definition):
            cns_item = schema.definition[name]
            key = u"{}___{}".format(schema.metadata["name"], cns_item["name"])
            map_src_property[key] = cns_item

    for schema in schema_list:
        for name in sorted(schema.definition):
            cns_item = schema.definition[name]
            #logging.info(cns_item)
            if "rdf:Property" in cns_item[u"@type"]:
                sheetname = "property"
            else:
                sheetname = "class"
            cns_item = _clean_list_value(cns_item)
            cns_item["statedIn"] = schema.metadata["name"]
            output_rows[sheetname].append(cns_item)
            output_columns[sheetname].update(cns_item.keys())

        sheetname = "template"
        for cns_item in schema.metadata["template"]:
            #logging.info(cns_item)
            if cns_item.get("version") == "":
                assert False
                continue

            cns_item = _clean_list_value(cns_item)
            cns_item["statedIn"] = schema.metadata["name"]
            del cns_item["name"]

            # add imported property's range and nameZh
            if cns_item.get("propertySchema"):
                #logging.info(json4debug(cns_item))
                key = u"{}___{}".format(cns_item["propertySchema"], cns_item["refProperty"])
                ref_property_definition =  map_src_property.get(key)
                #logging.info(json4debug(ref_property_definition))
                cns_item["propertyNameZh"] = ref_property_definition["nameZh"]
                cns_item["propertyRange"] = ref_property_definition["rdfs:range"]
                cns_item["propertyDefinitionZh"] = ref_property_definition.get("descriptionZh","")

            output_rows[sheetname].append(cns_item)
            output_columns[sheetname].update(cns_item.keys())

    """
    [
        {
            "sheetname": "sheet1",
            "columns": ["name","age"],
            "rows": [
                {"name":"john","age":30},
                {"name":"bob","age":20}
            ]
        },
        {
            "sheetname": "sheet2",
            "columns": ["color"],
            "rows": [
                {"color":"red"},
                {"color":"blue"}
            ]
        }
    ]
    """
    #logging.info(json4debug(output_rows))
    #assert False
    dataTable2018 = []
    for sheetname, rows in output_rows.items():
        if len(rows) == 0:
            continue

        columns = sorted(list(output_columns[sheetname]))

        sheet = {
            "sheetname": sheetname,
            "columns": columns,
            "rows": rows,
        }
        dataTable2018.append(sheet)

    if dataTable2018:
        json2excel4multiple(dataTable2018, filename_excel)


def _export_nquad(args, filename_output):
    from pyld import jsonld
    doc = file2json(filename_output)
    normalized = jsonld.normalize(
        doc, {'algorithm': 'URDNA2015', 'format': 'application/n-quads'})
    xdebug_file = os.path.join(args["debug_dir"],os.path.basename(args["output_file"]))
    filename_nquad = xdebug_file+u".nq"
    #filename_nquad = args["output_file"].replace("jsonld","nq")
    lines2file([normalized], filename_nquad )

    # RDF lib does not parse JSON-LD correctly
    #from rdflib import Graph, plugin
    #from rdflib.serializer import Serializer
    #testrdf = u"\n".join(file2iter(filename_output))
    #g = Graph().parse(data=testrdf, format='json-ld')
    #content = g.serialize(format='nt')
    #filename_ntriples = args["output_file"].replace("jsonld","nt")
    #lines2file([content], filename_ntriples )


if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--output_file': 'output file',
        '--debug_dir': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    excel2jsonld  and n-quad

    mv ~/Downloads/cns_top.xlsx ~/haizhi/git/kgtool/local/debug/
    python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/cns_top.xlsx --output_file=schema/cns_top.jsonld --debug_dir=local/debug/

    python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/cns_schemaorg.xls --output_file=schema/cns_schemaorg.jsonld --debug_dir=local/debug/

    python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/cns_fund_private.xlsx --output_file=schema/cns_fund_private.jsonld --debug_dir=local/debug/

    mv ~/Downloads/cns_organization.xlsx ~/haizhi/git/kgtool/local/
    python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/cns_organization.xlsx --output_file=schema/cns_organization.jsonld --debug_dir=local/debug/


"""
