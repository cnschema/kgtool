#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os
import sys
import json
import logging
import csv
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(".."))

from kgtool.core import *
from kgtool.stats import *

from kgtool.cns_model import preload_schema, CnsSchema, init_report
from kgtool.cns_validate import run_validate_recursive
from kgtool.cns_convert import run_convert

def task_load_data(args):
    logging.info("task_load_data")
    filename = args["input"]
    json_data = file2json(filename)
#    logging.info(len(json_data["@graph"]))
#    ret = stat_jsonld(json_data)
#    logging.info(json4debug(ret))
#    ret = stat_kg_pattern(json_data)
#    logging.info(json4debug(ret))

    schema_filename = args.get("input_schema")
    preloaded_schema_list = preload_schema(args)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(schema_filename, preloaded_schema_list)

    ret = []
    report = init_report()
    # stats
    for item in json_data["@graph"]:
        types = json_get_list(item, "@type")
        assert len (types) == 1
        main_type = types[0]
        report["stats"]["_type_{}".format(main_type)] +=1

    # prepare specialty
    map_id_item={}
    for item in json_data["@graph"]:
        types = json_get_list(item, "@type")
        assert len (types) == 1
        main_type = types[0]
        if main_type in ["Specialty"]:
            xid = item["@id"]
            cns_item = {"@type": ["Specialty", "CnsTag", "Thing"]}
            for p in ["@id","name", "nameZh"]:
                if item.get(p):
                    cns_item[p] = item[p]

            v_list = json_get_list(item, "parentItem")
            cns_item["broader"] = v_list
            for v in v_list:
                v["@type"] =["Specialty", "CnsTag", "Thing"]

            ret.append(cns_item)

    # convert scholar
    for item in json_data["@graph"]:
        types = json_get_list(item, "@type")
        assert len (types) == 1
        main_type = types[0]


        if main_type in ["Scholar"]:
            if not item.get("name"):
                logging.info(item)
                continue
            #logging.info(json4debug(item))

            types = ["Scholar", "Person", "Thing"]
            primary_keys = [item["@id"]]
            #convert
            #logging.info(json4debug(item))
            cns_item = convert_item(item)
            #logging.info(json4debug(cns_item))

            ret.append(cns_item)

    #validate
    run_validate_recursive(loaded_schema, ret, report)
    logging.info(json4debug(report))

    fileoutput = "local/output/kg4ai.jsonld"
    xid = "kg4ai-graph"
    jsonld_output = {
                "@context": {
                    "@vocab": "http://cnschema.org/"
                },
                "@id": any2sha256( xid ),
                "@type": ["Thing"],
                "name": xid,
                "@graph": ret }
    json2file(jsonld_output, fileoutput)
    #logging.info(len(ret))

MAP_ALIAS = {
    "name": "name",
    "nameZh": "nameZh",
    "image": "image",
    #"nationality": "nationality",
    "activity":"activeScore",	#活跃度值

    "totalCitation":"citationCount",	#总引用量
    "hIndex":"hIndex",	#
    "pubNumber": "publicationCount",	#出版物数量

    "bio": "description",
    "email": "email",
    "homepage": "website",	#个人主页
    "gender": "gender",	#
    "jobTitle": "jobTitle",	#
}

def convert_item(item):
    cns_item = {}
    for p,v in item.items():
        if v is None:
            continue

        if p == "@type":
            cns_item[p] = [v, "Thing"]
            continue

        if p == "@id":
            cns_item[p] = v
            continue


        p1 = MAP_ALIAS.get(p)
        if p1:
            if p1 == "nameZh":
                v = re.sub("\s","",v)

            if p1 == "activeScore":
                v = float(v)
            cns_item[p1] = v
            continue


        if isinstance(v, list):

            for vx in v:
                if  vx["@type"] == "Specialty":
                    vx["@type"] =["Specialty", "CnsTag", "Thing"]
                elif vx["@type"] == "Organization":
                    vx["@type"] =[ "Organization", "Thing"]
                    if vx.get("name"):
                        vx["@id"] = any2sha1( vx.get("name"))
                    else:
                        v.remove(vx)
                else:
                    assert False

            cns_item[p] = v
            continue

        if isinstance(v, dict):
            assert v["@type"] in ["Organization", "Country"]
            v["@type"] == [v["@type"], "Thing"]
            if v.get("name"):
                v["@id"] = any2sha1( v.get("name"))
                cns_item[p] = v
            else:
                del cns_item[p]
                pass

            continue


        logging.info(json4debug(item))
        logging.info(p)
        assert False
    return cns_item


def _update_content(item_csv, cns_item, entity_store, entity_store_csv, entity_store_csv_fields):
    for p,v in cns_item.items():
        if p == "@id":
            item_csv["_id:ID"] = v
            continue
        if p == "@type":
            item_csv["_type:LABEL"] = u";".join(json_get_list(cns_item, "@type"))
            continue

        if isinstance(v, dict):
            if "@id" in v:
                assert v["@id"] in entity_store["node"]
                link ={
                    "_in:START_ID": cns_item["@id"],
                    "_out:END_ID": v["@id"],
                    "_rel:TYPE": p,
                }
                entity_store_csv["link"].append(link)
                entity_store_csv_fields["link"].update(link.keys())
                continue
                pass
            else:
                item_csv[p] = json.dumps(v)
        elif isinstance(v, list):
            if v and isinstance(v[0], dict) and "@id" in v[0]:
                for vx in v:
                    link ={
                        "_in:START_ID": cns_item["@id"],
                        "_out:END_ID": vx["@id"],
                        "_rel:TYPE": p,
                    }
                    entity_store_csv["link"].append(link)
                continue
                pass
            elif v  == []:
                continue
            else:
                logging.info(v)
                item_csv[p] = u",".join(v)
        else:
            item_csv[p] = v


def task_jsonld4release(args=None):
    filename_output = "local/output/kg4ai.jsonld"
    json_data = file2json(filename_output)

    entity_store = collections.defaultdict(dict)

    # prepare node
    for cns_item in json_data["@graph"]:
        xid = cns_item["@id"]
        entity_store["node"][xid] = cns_item

    for cns_item in json_data["@graph"]:
        xid = cns_item["@id"]
        for p in cns_item:
            vlist = json_get_list(cns_item, p)
            if vlist and isinstance(vlist[0], dict) and "@id" in vlist[0]:
                for vx in vlist:
                    vid = vx["@id"]
                    if vid not in entity_store["node"]:
                        entity_store["node"][vid] = vx
                        logging.info("add sub stuff")


    #dump csv
    entity_store_csv = collections.defaultdict(list)
    entity_store_csv_fields = collections.defaultdict(set)
    for cns_item in entity_store["node"].values():
        item_csv = {}
        entity_store_csv["node"].append(item_csv)
        _update_content(item_csv, cns_item, entity_store, entity_store_csv, entity_store_csv_fields)
        entity_store_csv_fields["node"].update(item_csv.keys())

    for key, items in entity_store_csv.items():
        filename = "local/output/kg4ai.{}.csv".format(key)
        table2csv(items, sorted(list(entity_store_csv_fields[key])), filename)

    # dump jsons
    json_index = []
    for item in entity_store["node"].values():
        item_index = {"alternateName":[]}
        json_index.append(item_index)
        for p in ["name","@id","@type"]:
            if p not in item:
                logging.info(p)
                logging.info(item)
                #TODO there is one guy without name
                continue
            item_index[p] = item[p]

        for p in ["nameZh"]:
            if item.get(p):
                item_index["alternateName"].append(item[p])

    filename = "local/output/kg4ai.entity_index.json".format(key)
    items2file(json_index, filename)


def table2csv(items, fieldnames, filename):
    with open(filename, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=any2utf8(fieldnames), quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for item in items:
            temp = {}
            for field in fieldnames:
                temp[field] = item.get(field,"")
                if type(temp[field]) in [list] and temp[field] and type(temp[field][0]) in [basestring, str, unicode]:
                    temp[field] = ", ".join(temp[field])
                elif type(temp[field]) in [list] and temp[field] and type(temp[field][0]) in [dict]:
                    temp[field] = json4debug(temp[field])
                elif type(temp[field]) in [dict]:
                    temp[field] = json4debug(temp[field])
            #if '1361' in json4debug(temp) and  '"text"' in json4debug(temp):
            #    logging.info( json4debug(temp))
            #    logging.info( json4debug(any2utf8(temp)))
            #    raise False
            writer.writerow(any2utf8(temp))


if __name__ == '__main__':
    logging.basicConfig(format="[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s",
                        level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        "--input": "input data",
        "--input_schema": "input data",
        "--dir_schema": "input schema for preload",
        "--option": "option data",
    }
    main_subtask(__name__, optional_params=optional_params)

"""

    python example/kg4ai.py task_load_data --input=local/kg4ai_cn_1.0.1.jsondl --input_schema=local/schema/cns_kg4ai.jsonld --dir_schema=schema

    python example/kg4ai.py task_jsonld4release

    mkdir ~/my-software/neo4j-community-3.1.7/data/kg4ai
    rm -rf ~/my-software/neo4j-community-3.1.7/data/databases/graph.db
    rm ~/my-software/neo4j-community-3.1.7/data/kg4ai/*.csv

    cp local/output/kg4ai*csv  ~/my-software/neo4j-community-3.1.7/data/kg4ai
    ./bin/neo4j-import --multiline-fields=true --into ./data/databases/graph.db   --nodes ./data/kg4ai/kg4ai.node.csv  --relationships ./data/kg4ai/kg4ai.link.csv

    ./bin/neo4j restart

"""
