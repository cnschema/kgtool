# -*- coding: utf-8 -*-
# author: Li Ding


# base packages
import os
import sys
import json
import logging
import codecs
import hashlib
import datetime
import logging
import time
import argparse
import urlparse
import re
import collections
import copy

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

from kgtool.core import *
from kgtool.table import *
from kgtool.stats import stat_table
from cns.schemaorg import Schemaorg
from cns.cns_excel import init_cns_excel  # noqa

import requests
import requests_cache

def _clean_schemaorg_description(text):
    try:
         # Python 2.6-2.7
         from HTMLParser import HTMLParser
    except ImportError:
         # Python 3
         from html.parser import HTMLParser

    h = HTMLParser()

    temp = text
    temp = re.sub(ur"\n", " ", temp)
    #temp = re.sub(ur"Related .*$", "", temp)
    #temp = re.sub(ur"<ul.+$", "", temp)
    temp = re.sub(ur"<[^>]+>", "", temp)
    temp = re.sub(ur"\s+", " ", temp)
    #temp = re.sub("\n.*", "", temp)
    #temp = re.sub("\..+", ".", temp).strip()

    temp = h.unescape(temp)

    if not temp:
        logging.warning( temp )
    elif temp != text:
        logging.warning( text )
        logging.warning( temp )
    return temp

def _map_schemaorg():
    #rewerite schemaorg item
    pList = [{"name":"name", "alternateName":["rdfs:label"]},
            {"name":"category", "alternateName":["_group"]},
            {"name":"schemaorgUrl", "alternateName":["@id"]}]
    schemaorgItem = json_dict_copy(node, pList)

    p = "description"
    v = node.get("rdfs:comment","")
    v = _clean_schemaorg_description(v)
    schemaorgItem[p] = v

    schemaorgItem["version"] = version

    if "http://schema.org/supersededBy" in node:
        schemaorgItem["supersededBy"] = node["http://schema.org/supersededBy"]["@id"]

    return schemaorgItem

def task_load_schemaorg_translate(args=None, stats=None):
    if stats == None:
        stats = collections.Counter()

    version = args["version"]
    url_base = args["url_base"]

    #load translated version
    filename = "../local/schemaorg_translate.xlsx"
    filename = file2abspath(filename)
    temp = excel2json(filename)
    keys = temp["fields"][version]
    map_id_translate = {}
    for item in temp["data"][version]:
        stats["cnt_input_translate_version_{}".format(item["version"])] +=1
        stats["cnt_input_translate_category_{}".format(item["category"])] +=1
        schemaorg_id = item["schemaorgUrl"]
        map_id_translate[schemaorg_id] = item
    stats["cnt_input_translate"] = len(map_id_translate)

    logging.info(keys)
    return keys, map_id_translate


def task_make_cns_schemaorg(args=None, stats=None):
    if stats == None:
        stats = collections.Counter()

    map_id_node, final_item_list = task_update_schemaorg_translate(args, stats)

    pList= [
        {"name":"version"},
        {"name":"name"},
        {"name":"nameZh"},
        {"name":"alternateName"},
        {"name":"description"},
        {"name":"descriptionZh"},
        {"name":"supersededBy"},
        {"name":"", "alternateName":[]},
    ]

    list_sheet_name, mapDataTable = init_cns_excel()

    for item in final_item_list:
        #skip supersededBy concepts
        if item.get("supersededBy"):
            stats["cnt_skip_supersededBy"] +=1
            continue


        schemaorg_id = item["schemaorgUrl"]
        schemaorg_name = os.path.basename( schemaorg_id )
        schemaorgItem = map_id_node[schemaorg_id]

        cnsDefinition = json_dict_copy(item, pList)
        #logging.info(json4debug(item))
        if item["category"] == "type":
            sheetname = "class"
        elif item["category"] == "property":
            sheetname = "property"
        else:
            #not supported
            logging.info(json4debug(item))
            assert False
            continue

        stats["cnt_sheet_{}".format(sheetname)] += 1
        mapDataTable[sheetname]["rows"].append(cnsDefinition)

        # schemaorgItem
        p = "_super"
        if p in schemaorgItem:
            v = json_get_list(schemaorgItem, p)
            v = [x for x in v if x.startswith("http://schema.org/")]
            v = [os.path.basename(x)  for x in v]
            cnsDefinition["super"] = u", ".join(v)

            if len(v) > 1:
                logging.warn(u"more than one super {} {}".format( schemaorg_name, v ) )
                stats["warn_more_than_one_super"] += 1

        # p = "http://schema.org/domainIncludes"
        # if p in schemaorgItem:
        #     v = json_get_list(schemaorgItem, p)
        #     v = [x["@id"] for x in v]
        #     v = [x for x in v if x.startswith("http://schema.org/")]
        #     v = [os.path.basename(x) for x in v]
        #     cnsDefinition["domain"] = u", ".join(v)
        #
        #     if len(v) > 1:
        #         logging.warn(u"more than one domain {} {}".format( schemaorg_name, v ) )
        #         stats["warn_more_than_one_domain"] += 1


        #item
        p = "schemaorgUrl"
        v = item[p]
        v  = os.path.basename( v )
        cnsDefinition["schemaorgName"] = v

        p = "wikipediaUrl"
        if p in item:
            v = item[p]
            v  = os.path.basename( v )
            cnsDefinition["wikipediaName"] = v

        p = "version"
        cnsDefinition[p] = u"vso{}".format(item[p])

        p = "category"
        cnsDefinition[p] = u"{}-so".format(item[p]).replace("type","class")


    logging.info(json4debug(stats))
    filename_output = "../local/cns_schemaorg.xls"
    filename_output = file2abspath(filename_output, __file__)
    dataTable = [mapDataTable[x] for x in list_sheet_name ]
    json2excel4multiple( dataTable,  filename_output)

    return dataTable

def task_update_schemaorg_translate(args=None, stats=None):
    if stats == None:
        stats = collections.Counter()
    version = args["version"]
    url_base = args["url_base"]

    #load schemaorg
    so = Schemaorg(version, url_base)
    map_id_node = so.load_data()
    stats["cnt_input_schemaorg"] = len(map_id_node)

    #load translate
    keys, map_id_translate = task_load_schemaorg_translate(args, stats)

    #check existing duplicated name
    map_name_id = collections.defaultdict(set)
    for node in map_id_translate.values():
        if node["supersededBy"] != "":
            continue

        names = []
        names.append( node["name"] )
        names.append( node["nameZh"] )
        if node["alternateName"]:
            names.append( node["alternateName"] )
        for name in names:
            map_name_id[name].add( node["schemaorgUrl"] )

    for name, ids in map_name_id.items():
        if len(ids)>1:
            logging.warn(u"duplicated name {} ".format(name))
            stats["cnt_input_translate_duplicated"] += 1
    assert stats["cnt_input_translate_duplicated"]  == 0 , dict(stats)
    #logging.info(json4debug(map_name_id))
    #assert False

    #rebuild translated version

    final_item_list = []
    for node in sorted(map_id_node.values(), key=lambda x:(x["_group"], x["@id"]) ):
        schemaorg_id = node["@id"]
        stats["cnt_input_schemaorg_group_{}".format(node["_group"])] +=1


        if node["_group"] =="other":
            if not schemaorg_id.startswith("http://schema.org/"):
                stats["cnt_input_schemaorg_skip_other_nonschemaorg"] +=1
            stats["cnt_input_schemaorg_skip_other"] +=1
            continue



        stats["cnt_input_schemaorg_inuse"] +=1

        if "http://schema.org/supersededBy" in node:
            stats["cnt_input_schemaorg_inuse_supersededBy"] +=1

        #logging.info(json4debug(node))
        if schemaorg_id in map_id_translate:
            item = map_id_translate[schemaorg_id]
            final_item_list.append(item)
        else:
            final_item_list.append(_map_schemaorg(node))


    stats["cnt_input_final"] = len(final_item_list)

    assert stats["cnt_input_final"] == stats["cnt_input_schemaorg_inuse"]

    logging.info(json4debug(stats))
    filename_output = "../local/temp_schemaorg_translate.xls"
    filename_output = file2abspath(filename_output, __file__)
    json2excel( final_item_list, keys, filename_output)

    #final check if no more output can be produced
    assert stats["cnt_input_translate"] == stats["cnt_input_schemaorg_inuse"]

    return map_id_node, final_item_list

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)  # noqa
    logging.getLogger("requests").setLevel(logging.WARNING)

    filename = '../local/cache'
    filename = file2abspath(filename, __file__)
    requests_cache.install_cache(filename)

    optional_params = {
        '--version': 'schema.org version',
        '--url_base': 'schema.org version base URL',
    }
    main_subtask(__name__, optional_params=optional_params)


"""
    mv ~/Downloads/schemaorg_translate.xlsx ~/haizhi/git/kgtool/local/
    # prepare cns_schemaorg
    python cns/cns_schemaorg.py task_make_cns_schemaorg --version=3.4 --url_base=https://raw.githubusercontent.com/schemaorg/schemaorg/v3.4-release
    python cns/cns_excel.py task_excel2jsonld --input_file=local/cns_schemaorg.xls --output_file=schema/cns_schemaorg.jsonld --debug_dir=local/

    ~~~~~~~
    # load translate
    python cns/cns_schemaorg.py task_load_schemaorg_translate --version=3.4 --url_base=https://raw.githubusercontent.com/schemaorg/schemaorg/v3.4-release

    ~~~~~~~
    # update/validate translate

    #3.2 sdo-callisto
    python cns/cns_schemaorg.py task_update_schemaorg_translate --version=3.2 --url_base=https://raw.githubusercontent.com/schemaorg/schemaorg/sdo-callisto

    #3.3 sdo-enceladus
    python cns/cns_schemaorg.py task_update_schemaorg_translate --version=3.3 --url_base=https://raw.githubusercontent.com/schemaorg/schemaorg/v3.3-stable

    #3.4 sdo-telesto
    python cns/cns_schemaorg.py task_update_schemaorg_translate --version=3.4 --url_base=https://raw.githubusercontent.com/schemaorg/schemaorg/v3.4-release

    ~~~~~~~

"""
