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

# global constants
VERSION = 'v20180305'
CONTEXTS = [os.path.basename(__file__), VERSION]

from core import *  # noqa



def stat_items(items, option="list2sample"):
    ret = {"stat": collections.Counter() }
    if not type(items) == list:
        raise Exception("expect list of items")

    for idx, item in enumerate(items):
        ret["stat"]["cnt_total"]+=1

        if ret["stat"]["cnt_total"] == 1:
            #first line
            ret["sample"] = item2sample( item )


        for k,v in item2flatstr("", item, {}, option=option).items():
            if len(v) > 0:
                ret["stat"][u"cnt_key_{}".format(k)] += 1

    return ret


def stat_jsonld(data, key=None, counter=None):
    """
        provide statistics for jsonld, right now only count triples
        see also https://json-ld.org/playground/
        note:  attributes  @id @context do not contribute any triple
    """
    if counter is None:
        counter = collections.Counter()

    if isinstance(data, dict):
        ret = {}
        for k, v in data.items():
            stat_jsonld(v, k, counter)
            counter[u"p_{}".format(k)] += 0
        if key:
            counter["triple"] += 1
            counter[u"p_{}".format(key)] +=1
    elif isinstance(data, list):
        [stat_jsonld(x, key, counter) for x in data]
        if key in ["tag"]:
            for x in data:
                if isinstance(x, dict) and x.get("name"):
                    counter[u"{}_{}".format(key, x["name"])] +=1
                elif type(x) in [basestring, unicode]:
                    counter[u"{}_{}".format(key, x)] +=1

    else:
        if key and key not in ["@id","@context"]:
            counter["triple"] += 1
            counter[u"p_{}".format(key)] +=1

    return counter


def stat_kg_pattern(data, counter=None, level=0, flags=""):
    if counter == None:
        counter = collections.Counter()

    if type(data) in [list]:
        for item in data:
            stat_kg_pattern(item, counter, level)
        return counter
    elif type(data) in [dict]:
        stat_kg_pattern_entity(data, counter, level)

        ret = {}
        for p,v in data.items():
            if not "mergeFrom" in flags:
                # do not count merged from
                if p in "mergedFrom":
                    continue
            ret[p] = stat_kg_pattern(v, counter, level+1)
        return counter
    else:
        return counter

def stat_kg_pattern_entity(entity, counter, level):
    #validate
    if type(entity) != dict:
        key = u"error_entity_is_not_dict_{}".format(batch)
        counter[key]+=1
        return

    # get the most specific type of this entity
    # in cnschema, the first class in @type's list is the main class
    entity_domain = json_get_first_item(entity, "@type", "WarnNoType")

    # @type range
    if not entity.get("@type") in [list]:
        key = u"warn_type_not_list_{}".format(entity_domain)
        counter[key]+=1

    # @type
    key = u"type_all_{}".format(entity_domain)
    counter[key]+=1

    # root level entity
    if level == 0:
        key = u"type_level{}_{}".format(level,entity_domain)
        counter[key] += 1


    for p in entity:
        # domain
        key = u"domain_{}_{}".format(entity_domain, p)
        counter[key] += 1

        # range
        # do not proceed if p is mergedFrom
        if p in "mergedFrom":
            continue
        for v in json_get_list(entity, p):
            if type(v) not in [dict]:
                entity_range = "CNS_NONE"
                continue
            else:
                entity_range = json_get_first_item(v, "@type", "WarnNoType")

            key = u"range_{}_{}".format(p, entity_range)
            counter[key] += 1

def task_stat_kg_pattern(args):
    print "called task_stat_kg_pattern"
    logging.info(args)
    filenames = glob.glob(args["filepath"])
    logging.info(filenames)
    counter = collections.Counter()
    counter["_meta_timestamp"] = datetime.datetime.now().isoformat()[0:19]
    for filename in filenames:
        key = "_meta_files"
        counter[key]+=1
        for line in file2iter(filename):
            if not line:
                continue
            key = "_meta_lines"
            counter[key]+=1
            #logging.info(line)
            item = json.loads(line)
            counter = stat_kg_pattern(item, counter)
    logging.info(json4debug(counter))

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--filepath': 'input filepath',
        '--batch': 'batch id',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    generate sample data and statistics

    python kgtool/kg.py task_stat_kg_pattern --filepath=tests/*.jsons


"""
