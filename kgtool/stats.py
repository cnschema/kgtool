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

def stat_json_path(json_data, key, wm):
    xtype = type(json_data)
    if xtype  == dict:
        for k, v in json_data.items():
            if key:
                keynew = u"{}.{}".format(key, k)
            else:
                keynew = k

            stat_json_path(v, keynew, wm)

    elif xtype == list:
        for x in json_data:
            stat_json_path(x, key, wm)
    else:
        wm["count"][key] += 1

        if "sample" in wm and json_data!="" and len(wm["sample"][key]) < wm.get("MAX_SAMPLE", 3):
            wm["sample"][key].append(json_data)

        if "distribution" in wm:
            v = u"{}".format(json_data)
            if len(wm["distribution"][key]) >= wm.get("MAX_UNIQUE", 10):
                pass
            elif v in wm["distribution"][key]:
                wm["distribution"][key][v] += 1
            else:
                wm["distribution"][key][v] = 1
                wm["unique"][key] += 1


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
        key = u"ErrorEntityIsNotDict_{}".format(batch)
        counter[key]+=1
        return

    # get the most specific type of this entity
    # in cnschema, the first class in @type's list is the main class
    entity_domain = json_get_first_item(entity, "@type", "WarnNoType")

    # @type range
    if isinstance(entity.get("@type"), list ):
        key = u"Warn@TypeIsNotList_{}".format(entity_domain)
        #print (json4debug(counter))
        counter[key]+=1

    # @type
    key = u"typeAll_{}".format(entity_domain)
    counter[key]+=1

    # root level entity
    if level == 0:
        key = u"typeLevel{}_{}".format(level,entity_domain)
        counter[key] += 1

    if "in" in entity and "out" in entity and isinstance(entity["in"], dict):
        main_type_in = json_get_list(entity["in"],"@type")[0]
        main_type_out = json_get_list(entity["out"],"@type")[0]
        main_type_link = json_get_list(entity,"@type")[0]
        key = u"cnslink_{}_[{}]_{}".format(main_type_in,main_type_link, main_type_out)
        counter[key] += 1

    for p, values in entity.items():
        # domain
        key = u"template_{}_{}".format(entity_domain, p)
        counter[key] += 1

        assert values is not None

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

def stat_kg_report_per_item(cns_item, cns_item_category, stat_counter, flag_count_triple = False, map_entity = {}):
    if cns_item_category == None:
        if "CnsLink" in cns_item["@type"]:
            cns_item_category = "relation"
        else:
            cns_item_category = "entity"


    stat_counter["_cnt_kg_item_all"] += 1
    stat_counter["_cnt_kg_item_all_{}".format(cns_item_category)] += 1

    #count triple
    if flag_count_triple:
        ret = stat_jsonld(cns_item)
        stat_counter["_cnt_kg_triple"] += ret["triple"]
        stat_counter["_cnt_kg_triple_{}".format(cns_item_category)] += ret["triple"]

    #count data
    etype = cns_item["@type"][0]
    stat_counter[u"_cnt_kg_item_type_{}".format(etype)] += 1

    for k in cns_item:
        stat_counter[u"_cnt_{}_template_{}_{}".format(cns_item_category, etype, k)] += 1

    # count domain range
    if cns_item_category == "relation" and map_entity:
        rtype = cns_item["@type"][0]
        in_type = map_entity.get(relation["in"])["@type"][0]
        out_type = map_entity.get(relation["out"])["@type"][0]
        stat_coutner[u"_cnt_cnslink_{}_[{}]_{}".format(in_type, rtype, out_type)] += 1


def _json_clone(data, keys, flag_deepcopy=False):
    ret = {}
    for k,v in data.items():
        if k in keys:
            ret[k] = v
    return ret

def stat_kg_summary(list_entity, list_relation, dirname, max_sample = 5, flag_map_entity = True, schema_for_validation = None):
    assert os.path.exists(dirname), dirname

    property_list_tiny = set([ "@type", "name"])
    property_list_sample = set(["@id", "@type", "name", "alternateName", "statedIn", "identifier"])

    list_conf = [
        {"cns_item_category": "entity", "cns_item_list": list_entity},
        {"cns_item_category": "relation", "cns_item_list": list_relation}
    ]

    map_entity = {}
    stat_counter = collections.Counter()
    samples = collections.defaultdict(list)
    if schema_for_validation:
        report = schema_for_validation.init_report()
    else:
        report = {}

    for conf in list_conf:
        for cns_item in conf["cns_item_list"]:
            cns_item_category = conf["cns_item_category"]

            main_type = cns_item["@type"][0]
            if "CnsLink" in cns_item["@type"]:
                assert cns_item_category == "relation"
            else:
                assert cns_item_category == "entity"

            stat_kg_report_per_item(cns_item, cns_item_category, stat_counter)

            if schema_for_validation:
                schema_for_validation.run_validate(cns_item, report)

            #basic validation
            for p in ["@id","@type"]:
                assert p in cns_item, p

            if flag_map_entity and cns_item_category == "entity" :
                cns_item_tiny = _json_clone( cns_item, property_list_tiny )
                map_entity[cns_item["@id"]] = cns_item_tiny

            #collect samples
            key  = u"sample_{}_{}".format(cns_item_category, main_type)
            cns_item_sample = _json_clone( cns_item, property_list_sample )
            if len(samples[key]) < max_sample:
                samples[key].append(cns_item_sample)

            key  = u"all_{}_{}".format(cns_item_category, main_type)
            samples[key].append(cns_item_sample)

    for key, data in samples.items():
        filename = u"{}/{}.json".format(dirname, key)
        #filename = file2abspath(filename, __file__)
        json2file(data, filename)


    filename = u"{}/summary.json".format(dirname)
    #filename = file2abspath(filename, __file__)
    ret = {"stats":stat_counter, "report": report}
    json2file(ret, filename)

    return report


def task_stat_json_path(args):
    logging.info(args)
    filenames = glob.glob(args["filepath"])

    wm = {
        "count":collections.Counter(),
        "unique":collections.Counter(),
        "sample": collections.defaultdict(list),
        "distribution": collections.defaultdict(dict),
    }

    if args.get("option") == "jsons":
        for filename in filenames:
            key = "_meta_files"
            wm["count"][key]+=1
            for line in file2iter(filename):
                if not line:
                    continue

                key = "_items"
                wm["count"][key]+=1
                if wm["count"][key] % 10000 == 0:
                    logging.info(json4debug(wm["count"]))

                try:
                    item = json.loads(line)
                    stat_json_path(item, "", wm)
                except:
                    wm["count"][u"warn_skip_lines"] += 1
                    wm["count"][u"warn_skip_lines_{}".format(os.path.basename(filename))] +=1
    else:
        for filename in filenames:
            key = "_meta_files"
            wm["count"][key]+=1

            item = file2json(filename)

            key = "_items"
            wm["count"][key]+=1
            if wm["count"][key] % 10000 == 0:
                logging.info(json4debug(wm["count"]))

            stat_json_path(item, "", wm)

    # print result
    ret = collections.defaultdict(dict)
    for key in wm:
        if key in "distribution":
            continue
        for p,v in wm[key].items():
            ret[p][key] = v

    logging.info(json4debug(ret))
    logging.info(json4debug(wm["count"]))

    filename = args.get("output")
    if filename:
        json2file(ret, filename)

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--filepath': 'input filepath',
        '--output': 'output filename',
        '--option': 'json jsons',
        '--cprofile': 'cprofile',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    generate sample data and statistics

    python kgtool/stats.py task_stat_kg_pattern --filepath=local/jsons/*.jsons --output=local/output/test_kg_stat.json

    python kgtool/stats.py task_stat_json_path --filepath=tests/test_stats_kg1.jsons --option=jsons --output=local/output/test_stat_json_path.json
    python kgtool/stats.py task_stat_json_path --filepath=local/jsons/*.jsons --option=jsons --output=local/output/test_stat_json_path.json
    python kgtool/stats.py task_stat_json_path --filepath=schema/*.jsonld --option=json --output=local/output/test_stat_json_path.json

    python kgtool/stats.py task_stat_json_path --filepath=local/jsons/*.jsons --option=jsons --output=local/output/test_stat_json_path.json --cprofile=yes

"""
