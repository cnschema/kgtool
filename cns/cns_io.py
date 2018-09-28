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


* excel2jsonld
* jsonld2model with schema validation
* data validation

table -> jsonld -> mem


excel -> table2mem -> memschema
jsonld -> jsonld2mem -> memschema
memschema -> mem2jsonld -> jsonld
memschema -> mem2table -> excel

"""

def task_excel2jsonld(args):
    schema_excel_filename = args["input_file"]
    options = "table_single,table_import"
    output_json = excel2schema(schema_excel_filename, None, options)

    #read table from excel, and convert them into mem model
    if not output_json["result"]:
        logging.info(json4debug(output_json["validation_report"]))
        return False


    filename_output = os.path.join(args["output_dir"], output_json["jsonld"]["identifier"]+".jsonld")
    json2file(output_json["jsonld"], filename_output)

    #export table and then store that in excel
    filename_output = os.path.join(args["debug_dir"], output_json["jsonld"]["identifier"]+".export.single.xls")
    json2excel4multiple(output_json["table_single"], filename_output)

    filename_output = os.path.join(args["debug_dir"], output_json["jsonld"]["identifier"]+".export.import.xls")
    json2excel4multiple(output_json["table_import"], filename_output)


def excel2schema(schema_excel_filename, schema_urlprefix, options):
    schema_excel_json = excel2json2018(schema_excel_filename)

    return table2schema(schema_excel_json, schema_urlprefix, options)


def table2schema(schema_excel_json, schema_urlprefix, options):

    output_json = {}

    converter = CnsModelTable()
    converter.schema.schema_urlprefix = schema_urlprefix

    #read table from excel, and convert them into mem model
    if not converter.table2mem(schema_excel_json):
        logging.info(json4debug(converter.report.data))
        output_json["result"] = False
        output_json["validation_report"] = converter.report.data
        return output_json

    the_schema = converter.schema

    #mem2jsonld
    json_data = the_schema.mem2jsonld()
    output_json["jsonld"] = json_data

    temp = mem4export(the_schema, schema_urlprefix, options)
    output_json.update( temp )

    return output_json


def schema4export(schema_release_identifier, schema_urlprefix, options, preloaded_schema_list):
    jsonld = load_jsonld(schema_release_identifier, schema_urlprefix, None)
    the_schema = CnsSchema()
    the_schema.jsonld2mem(jsonld, preloaded_schema_list)
    return mem4export(the_schema, schema_urlprefix, options)

def mem4export(the_schema, schema_urlprefix, options):
    output_json = {}

    output_json["result"] = not the_schema.report.has_bug()
    output_json["schema_name"] = the_schema.metadata["name"]
    output_json["schema_version"] = the_schema.metadata["version"]
    output_json["schema_identifier"] = the_schema.metadata["identifier"]
    output_json["validation_report"] = the_schema.report.data

    if options:
        if "dot" in options:
            dot_file_map = run_graphviz(the_schema, graph_name, ctx)

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

    logging.info(options)
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
