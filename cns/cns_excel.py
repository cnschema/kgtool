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
from kgtool.table import excel2json2018, json2excel,json2excel4multiple  # noqa
from kgtool.cns_model_table import CnsModelTable, mem2table


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
    filename_input = args["input_file"]
    excel_data = excel2json2018(filename_input)

    converter = CnsModelTable()

    #read table from excel, and convert them into mem model
    if not converter.table2mem(excel_data):
        logging.info(json4debug(converter.report.data))
        return False
    the_schema = converter.schema

    #mem2jsonld
    filename_output = os.path.join(args["output_dir"], the_schema.metadata["identifier"]+".jsonld")
    logging.info(filename_output)
    json_data = the_schema.mem2jsonld(filename_output)

    #_export_nquad(args, filename_output)

    #export table and then store that in excel
    filename_output = os.path.join(args["debug_dir"], the_schema.metadata["identifier"]+".export.clean.xls")
    dataTable2018 = mem2table(the_schema,  flag_import=False)
    json2excel4multiple(dataTable2018, filename_output)

    filename_output = os.path.join(args["debug_dir"], the_schema.metadata["identifier"]+".export.import.xls")
    dataTable2018 = mem2table(the_schema,  flag_import=True)
    json2excel4multiple(dataTable2018, filename_output)



def run_excel2mem(excel_data):

    #jsonld2mem
    if not the_schema.build():
        logging.info(json4debug(the_schema.report))
        return False

    #mem2jsonld
    json_data = the_schema.mem2jsonld()

    #validate4jsonld
    run_validate_recursive(the_schema, json_data, the_schema.report)
    if len(the_schema.report["bugs_sample"]) > 0:
        logging.info(json4debug(the_schema.report))
        return False

    return the_schema

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
        '--debug_dir': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    excel2jsonld  and n-quad

    mv ~/Downloads/cns_top.xlsx ~/haizhi/git/kgtool/local/debug/
    python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/cns_top.xlsx --output_dir=schema/ --debug_dir=local/debug/

    mv ~/Downloads/cns_organization.xlsx ~/haizhi/git/kgtool/local/
    python cns/cns_excel.py task_excel2jsonld --input_file=local/debug/cns_organization.xlsx --output_dir=schema/ --debug_dir=local/debug/



"""
