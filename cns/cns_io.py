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
import re
import collections
import glob
import copy
import urllib

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

from kgtool.core import *  # noqa
from kgtool.table import excel2json2018, json2excel,json2excel4multiple  # noqa
from kgtool.cns_model_table import CnsModelTable, mem2table
from kgtool.cns_graphviz import run_graphviz

# global constants
VERSION = 'v20180919'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
* load CnSchema instance
* dump in json for version checking
* generate information quality report
* draw schema diagram
* maintain property mapping


KGTOOL API

* excel2schema  excel file to schema, and generate schema output format
* table2schema  excel table json to schema, and generate schema output format
* schema4export schema to output format

"""

def excel2schema(schema_excel_filename, schema_urlprefix, options):
    """ given an excel filename, convert it into memory object,
        and output JSON representation based on options.

        params:
            schema_excel_filename -- string, excel filename
            schema_urlprefix -- string,   urlprefix for downloading schema's jsonld
                                ie. the jsonld version of schema can be obtained from URL

                                <code><schema_urlprefix><schema_release_identifier>.jsonld</code>,

                                e.g.  http://localhost:8080/getschema/cns_top_v2.0.jsonld
                                { schema_urlprefix = http://localhost:8080/getschema/
                                  schema_release_identifier = cns_top_v2.0
                                  schema_name = cns_top
                                  schema_vesrion = v2.0
                                }
            options -- string, comma seperated strings, each define expected output component, see <code>mem4export</code>

        return  json dict   see mem4export
    """
    schema_excel_json = excel2json2018(schema_excel_filename)

    return table2schema(schema_excel_json, schema_urlprefix, options)


def table2schema(schema_excel_json, schema_urlprefix, options):
    """ given an excel table json object, convert it into memory object,
        and output JSON representation based on options.

        params:
            schema_excel_filename -- string, excel filename
            schema_urlprefix -- string,   urlprefix for downloading schema's jsonld

        return  json dict   see mem4export
    """
    output_json = {}

    converter = CnsModelTable()
    converter.schema.schema_urlprefix = schema_urlprefix

    #read table from excel, and convert them into mem model
    if not converter.table2mem(schema_excel_json):
        logging.info(json4debug(converter.report.data))
        output_json["validation_result"] = not converter.report.has_bug()
        output_json["validation_report"] = converter.report.data
        return output_json

    temp = mem4export(converter.schema, options)
    output_json.update( temp )

    return output_json


def schema4export(schema_release_identifier, schema_urlprefix, options, preloaded_schema_list):
    """ given a jsonld version of schema, convert it into memory object,
        and output JSON representation based on options.

        params:
            schema_release_identifier -- string, ontology_release's identifier
            schema_urlprefix -- string,   urlprefix for downloading schema's jsonld
            options -- string, comma seperated strings, each define expected output component, see <code>mem4export</code>
            preloaded_schema_list -- optional, a list of JSONLD that contains imported schema_release

        return  json dict   see mem4export
    """
    jsonld = load_jsonld(schema_release_identifier, schema_urlprefix, None)
    the_schema = CnsSchema()
    the_schema.schema_urlprefix = schema_urlprefix
    the_schema.jsonld2mem(jsonld, preloaded_schema_list)
    return mem4export(the_schema, schema_urlprefix, options)

def mem4export(the_schema, options):
    """ export schema memory object into different exchange formats in json format.

        params:
            the_schema -- CnsSchema,  an memory object that contains the schema and its index
            options -- string, comma seperated strings, each define expected output component, see <code>mem4export</code>
                e.g.  jsonld,table_single,dot_compact,dot_import

                * jsonld   -- jsonld version of schema

                * dot_compact   -- graphviz dot file, compact mode, just itself, exclude CnsAttribute
                * dot_full      -- graphviz dot file, full mode, just itself, everything,
                                    i.e. Thing, CnsLink, CnsAttribute, DataType, CnsDataStructure
                                    and subClassOf, subPropertyOf,
                * dot_import    -- graphviz dot file, import mode, include all imported ontology release
                                    classes/property are blocked by the ontology relase box that defined them
                * table_single      -- in table2018 format(see table.py), schema itself only
                * table_import      -- in table2018 format(see table.py), schema itself and all its imported schema

        returns  json-dict

            {
                "identifier": "cns_top_v2.0",
                "name": "cns_top",
                "version": "v2.0",

                "validation_result": True,
                "validation_report":{},

                "jsonld": {},
                "dot_compact": "",
                "dot_full": "",
                "dot_import": "",
                "table_single": "",
                "table_import": ""
            }
    """
    output_json = {}

    output_json["validation_result"] = not the_schema.report.has_bug()
    output_json["schema_name"] = the_schema.metadata["name"]
    output_json["schema_version"] = the_schema.metadata["version"]
    output_json["schema_identifier"] = the_schema.metadata["identifier"]
    output_json["validation_report"] = the_schema.report.data

    if options:
        if "dot" in options:
            graph_name = re.sub(r"[-\.]","_", output_json["schema_identifier"])
            dot_file_map = run_graphviz(the_schema, graph_name)

        for option in [x.strip() for x in options.split(",")]:
            if option == "dot_compact":
                output_json[option] = dot_file_map[option]
            elif option == "dot_import":
                output_json[option] = dot_file_map[option]
            elif option == "dot_full":
                output_json[option] = dot_file_map[option]
            elif option == "table_single":
                output_json[option] = mem2table(the_schema,  flag_import=False)
            elif option == "table_import":
                output_json[option] = mem2table(the_schema,  flag_import=True)
            elif option == "jsonld":
                json_data = the_schema.mem2jsonld()
                output_json[option] = json_data

    #logging.info(options)
    logging.info(output_json.keys())
    return output_json

def _export_nquad(args, filename_output):
    from pyld import jsonld
    doc = file2json(filename_output)
    normalized = jsonld.normalize(
        doc, {'algorithm': 'URDNA2015', 'format': 'application/n-quads'})
    xdebug_file = os.path.join(args["debug_dir"],os.path.basename(filename_output))
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







def task_excel2jsonld(args):
    schema_excel_filename = args["input_file"]
    options = "jsonld,table_single,table_import,dot_compact,dot_import,dot_full"
    output_json = excel2schema(schema_excel_filename, None, options)

    #read table from excel, and convert them into mem model
    if not output_json["validation_result"]:
        logging.info(json4debug(output_json["validation_report"]))
        return False

    #validateJsonDump(output_json["jsonld"])

    filename_output = os.path.join(args["output_dir"], output_json["jsonld"]["identifier"]+".jsonld")
    json2file(output_json["jsonld"], filename_output)

    #export table and then store that in excel
    for p in ["table_single", "table_import"]:
        filename_output = os.path.join(args["debug_dir"], output_json["jsonld"]["identifier"]+"."+p+".xls")
        json2excel4multiple(output_json[p], filename_output)

        filename_output = os.path.join(args["debug_dir"], output_json["jsonld"]["identifier"]+"."+p+".json")
        json2file(output_json[p], filename_output)

    #dot file
    for p in ["dot_compact", "dot_full", "dot_import"]:
        filename_output = os.path.join(args["debug_dir"], output_json["jsonld"]["identifier"]+"."+p[4:]+".dot")
        lines2file([output_json[p]], filename_output)


if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--output_dir': 'output file',
        '--schema_dir': 'output file',
        '--debug_dir': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    excel2jsonld  and n-quad

    mv ~/Downloads/cns_top.xlsx ~/haizhi/git/kgtool/local/debug/
    python cns/cns_io.py task_excel2jsonld --input_file=local/debug/cns_top.xlsx --schema_dir=schema/ --output_dir=schema/ --debug_dir=local/debug/

    mv ~/Downloads/cns_organization.xlsx ~/haizhi/git/kgtool/local/
    python cns/cns_io.py task_excel2jsonld --input_file=local/debug/cns_organization.xlsx --output_dir=schema/ --debug_dir=local/debug/



"""
