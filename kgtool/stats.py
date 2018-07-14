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


def stat_table(items, unique_fields, value_fields=[], printCounter=True, MAX_UNIQUE = 100, REPORT_GAP = 10000):
    counter = collections.Counter()
    unique_counter = collections.defaultdict(list)

    for idx, item in enumerate(items):
        if idx % REPORT_GAP == 0:
            logging.info(u"{} {}".format(idx, json4debug(item) ))

        counter["all"] += 1
        # add no more than MAX_UNIQUE unique value
        for field in unique_fields:
            v = item.get(field)
            if v is not None:
                if v not in unique_counter[field]:
                    if len(unique_counter[field]) < MAX_UNIQUE:
                        unique_counter[field].append(v)
        # count
        for field in value_fields:
            value = item.get(field)
            value = normalize_value(value)
            if value is not None:
                counter[u"all_{}_nonempty".format(field)] += 1
                if value in unique_counter[field]:
                    counter[u"pv_{}_{}".format(field, value)] += 1

        # count unique value
        for field in unique_fields:
            counter[u"all_{}_unique".format(field)] = len(unique_counter[field])

    if printCounter:
        logging.info(json.dumps(counter, ensure_ascii=False,
                                indent=4, sort_keys=True))

    return counter

def stat_sample(items):
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
                     assert type(v) == list
                     counter["total_mergedFrom_out"] += len(v)
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
        #print (json4debug(counter))
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
            if counter[key] % 10000 == 0:
                logging.info(json4debug(counter))

            #logging.info(line)
            try:
                item = json.loads(line)
            except:
                counter[u"warn_skip_lines"] += 1
                counter[u"warn_skip_lines_{}".format(os.path.basename(filename))] +=1
                continue
            else:
                counter = stat_kg_pattern(item, counter)

    # print result
    logging.info(json4debug(counter))

    #write to output
    filename = args.get("output")
    if filename:
        # save result to file
        json2file(counter, filename)

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--filepath': 'input filepath',
        '--output': 'output filename',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    generate sample data and statistics

    python kgtool/stat.py task_stat_kg_pattern --filepath=tests/*.jsons --output=local/test_kg_stat.json


"""
