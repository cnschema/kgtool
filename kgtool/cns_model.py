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
from difflib import unified_diff

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

from kgtool.core import *  # noqa
from kgtool.alg_graph import DirectedGraph

# global constants
VERSION = 'v20180729'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
cnSchema data model (storage and index)
 * definition: defintion of a class, property, or a constant
 * metadata: list of template, changelog

cnSchema data loader
   * load class/property set_definition
   * load template restriction metadata
   * load version metadata
   * validate unique name/alias of class/property,
"""

def gen_cns_link_default_primary_key(cns_item):
    assert cns_item["@type"]
    assert isinstance(cns_item["@type"], list)
    assert "CnsLink" in cns_item["@type"]
    assert "in" in cns_item
    assert "out" in cns_item
    ret = [ cns_item["@type"][0] ]
    for p in ["in","out","date","identifier","startDate", "endDate"]:
        ret.append( cns_item.get(p,""))
    #logging.info(ret)
    return ret

def gen_cns_id(cns_item, primary_keys=None):
    if "@id" in cns_item:
        return cns_item["@id"]
    elif primary_keys:
        return any2sha256(primary_keys)
    elif "CnsLink" in cns_item["@type"]:
        return any2sha256(gen_cns_link_default_primary_key(cns_item))
    else:
        raise Exception("unexpected situation")  # unexpected situation


def gen_plist(cns_item, plist_meta=None):
    #if 'rdfs:domain' in cns_item:
    #    domains = parse_list_value(cns_item["rdfs:domain"])
    #else:
    #    assert False, cns_item
    if plist_meta is None:
        plist_meta = [ {"name":"name", "alternateName":["refProperty"]},
                       {"name":"alternateName", "alternateName":["propertyAlternateName"]}]

    plist = json_dict_copy(cns_item, plist_meta)
    assert plist["name"], cns_item

    plist["alternateName"] = parse_list_value( plist.get("alternateName", []) )
    for p,v in cns_item.items():
        if p == "name":
            continue

        name = None
        if p.startswith("name"):
            name = v
        elif p.startswith("propertyName"):
            name = v
        if name and name not in plist["alternateName"]:
            plist["alternateName"].append( name )

    return plist

def gen_imported_schema_list(schema, preloaded_schema_list):
    #handle import
    name = schema.metadata["name"]
    imported_schema_list = []
    imported_schema_name = []
    if name != "cns_top":
        imported_schema_name.append( "cns_top" )

    #logging.info(json4debug(schema.metadata))
    imported_schema_name.extend( json_get_list(schema.metadata, "import") )
    #logging.info(json4debug(schema.metadata["import"]))
    #assert False

    #logging.info(json4debug(imported_schema_name))
    for schema_name in imported_schema_name:
        schema = preloaded_schema_list.get(schema_name)
        if not schema:
            #load schema on demand
            filename = u"../schema/{}.jsonld".format(schema_name)
            filename = file2abspath(filename)
            logging.info("import schema "+ filename)
            schema = CnsSchema()
            schema.import_jsonld(filename, preloaded_schema_list)

        assert schema, schema_name
        imported_schema_list.append( schema )
        logging.info("importing {}".format(schema_name))
    return imported_schema_list

def init_report():
    return  {"bugs":[], "bugs_sample":{},"stats":collections.Counter(), "flag_detail": False}


def write_report(report, bug):
    key = ur" | ".join([bug["category"], bug["text"], bug.get("class",""), bug.get("property","")])
    report["stats"][key]+=1
    if key not in report["bugs_sample"]:
        report["bugs_sample"][key] = copy.deepcopy(bug)

    if report.get("flag_detail"):
        msg = json.dumps(bug, ensure_ascii=False, sort_keys=True)
        report["bugs"].append(bug)
        logging.info(msg)

def gen_range_validation_config(range_text, schema):
    temp = {"text": range_text, "python_type_value_list":[], "cns_range_entity":[], "cns_range_datastructure":[]}
    for r in parse_list_value(range_text):
        if range_text.lower() in ["text", "date", "datetime", "number", "url"]:
            temp["python_type_value_list"].extend([basestring,unicode,str])
        elif range_text.lower() in ["integer"]:
            temp["python_type_value_list"].append(int)
        elif range_text.lower() in ["float"]:
            temp["python_type_value_list"].append(float)
        elif "CnsDataStructure" in schema.index_inheritance["rdfs:subClassOf"].get(r,[]):
            temp["cns_range_datastructure"].append( range_text )
        else:
            temp["cns_range_entity"].append( range_text )

    return temp

class CnsSchema:
    def __init__(self):
        # Schema raw data: metadata information, key => value
        # version
        # template
        self.metadata = collections.defaultdict(list)

        # Schema raw data: concept definition,  @id => entity
        self.definition = collections.defaultdict(dict)

        # all schema module, includion self
        self.loaded_schema_list = []

        #index: 属性名称映射表  property alias => property standard name
        self.index_property_alias = {}

        #index: 定义名称映射表  defintion alias => definition（property/class）
        self.index_definition_alias = {}

        #index: VALIDATION  class => template Object
        self.index_validate_template = collections.defaultdict( dict )

        #index: VALIDATION  property => expected types
        self.index_validate_domain = collections.defaultdict( list )

        #index: VALIDATION  property =>  range
        self.index_validate_range = collections.defaultdict( dict )

        #index: subclass/subproperty inheritance  class/property to all its super ones
        self.index_inheritance = collections.defaultdict(dict)


    def set_definition(self, item):
        assert "@id" in item
        self.definition[item["@id"]]  = item

    def get_definition(self, xid):
        return self.definition.get(xid)

    def get_definition_by_alias(self, alias):
        return self.index_definition_alias.get(alias)

    def add_metadata(self, group, item):
        if group in ["version", "template"]:
            self.metadata[group].append(item)
        elif group in ["import"]:
            if type(item) == list:
                self.metadata[group].extend(item)
            else:
                self.metadata[group].append(item)
        else:
            self.metadata[group] = item


    def build(self, preloaded_schema_list={}):

        available_schema_list = []
        #available_schema_list.extend( self.imported_schema_list )
        available_schema_list.extend(gen_imported_schema_list(self, preloaded_schema_list))
        available_schema_list.append(self)

        self.loaded_schema_list = available_schema_list
        #logging.info(available_schema_list[0].metadata["name"])
        #assert False

        #if self.metadata['name'] == "cns_fund_public":
        #    logging.info(self.metadata['name'] )
        #    logging.info([x.metadata["name"] for x in available_schema_list])
        #    assert False

        self._build_index_property_alias(available_schema_list)
        self._build_index_definition_alias(available_schema_list)
        self._build_index_inheritance(available_schema_list)
        self._build_index_range(available_schema_list)
        self._build_index_template(available_schema_list)
        self._build_index_domain(available_schema_list)

        #logging.info([x.metadata["name"] for x in available_schema_list])
        self._validate_schema()

        return self._stat()



    def _validate_schema(self):
        for template in self.metadata["template"]:
            cls = self.index_definition_alias.get( template["refClass"] )
            #logging.info(json4debug(sorted(self.index_definition_alias.keys())))
            assert cls, template # missing class definition
            assert cls["name"] == template["refClass"]
            assert cls["@type"][0] == "rdfs:Class"

            prop = self.index_definition_alias.get( template["refProperty"] )
            assert prop, template  #  refProperty not defined
            assert prop["name"] == template["refProperty"]
            assert prop["@type"][0] == "rdf:Property"

    def _stat(self):
        stat = collections.Counter()
        for cnsItem in self.definition.values():
            if "rdf:Property" in cnsItem["@type"]:
                stat["cntProperty"] +=1
            elif  "rdfs:Class" in cnsItem["@type"]:
                stat["cntClass"] +=1

        stat["cntTemplate"] += len(self.metadata["template"])

        stat["cntTemplateGroup"] += len(set([x["refClass"] for x in self.metadata["template"]]))

        ret = {
            "name" : self.metadata["name"],
            "stat" : stat
        }
        logging.info( ret )
        return ret

    def _build_index_inheritance(self, available_schema_list):
        #list all direct class hierarchy pairs
        plist = ["rdfs:subClassOf","rdfs:subPropertyOf"]
        direct_sub = collections.defaultdict(list)
        for schema in available_schema_list:
            for cns_item in schema.definition.values():
                for p in plist:
                    if p in cns_item:
                        for v in cns_item[p]:
                            direct_sub[p].append([cns_item["name"], v])

        #logging.info(json4debug(direct_sub))

        # compute indirect class hierarchy relations
        self.index_inheritance = collections.defaultdict(dict)
        for p in direct_sub:
            dg = DirectedGraph(direct_sub[p])
            self.index_inheritance[p] = dg.compute_subtree()

        #complete with all definition
        for cns_item in schema.definition.values():
            if "rdf:Property" in cns_item["@type"]:
                p = "rdfs:subPropertyOf"
            else:
                p = "rdfs:subClassOf"
            n = cns_item["name"]
            if n not in self.index_inheritance[p]:
                self.index_inheritance[p][n] = [n]

        #logging.info( json4debug(self.index_inheritance ))


    def _build_index_range(self, available_schema_list):
        #reset
        self.index_validate_range = {}

        #init system property
        self.index_validate_range["@id"] = {"text": "UUID", "python_type_value_list":[basestring,unicode,str]}
        self.index_validate_range["@type"] = {"text": "Text", "python_type_value_list":[basestring,unicode,str]}
#        self.index_validate_range ["@context"] = {"text": "SYS", "cns_range_list": []}
        self.index_validate_range["@graph"] = {"text": "SYS", "cns_range_list": ["CnsMetadata"]}
        self.index_validate_range["rdfs:domain"] = {"text": "SYS", "python_type_value_list":[basestring,unicode,str]}
        self.index_validate_range["rdfs:range"] = {"text": "SYS", "python_type_value_list":[basestring,unicode,str]}
        self.index_validate_range["rdfs:subClassOf"] = {"text": "SYS", "python_type_value_list":[basestring,unicode,str]}
        self.index_validate_range["rdfs:subPropertyOf"] = {"text": "SYS", "python_type_value_list":[basestring,unicode,str]}

        #build
        for schema in available_schema_list:
            for cns_item in schema.definition.values():
                if cns_item["name"] in ["@id", "@type"]:
                    assert False, json4debug(cns_item)

                if "rdf:Property" in cns_item["@type"] and "rdfs:range" in cns_item:
                    #logging.info(json4debug(cns_item))
                    p = cns_item["name"]
                    r = cns_item["rdfs:range"]
                    #assert type(r) == list
                    if not p in self.index_validate_range:
                        temp = {"text": r}
                        if r in ["Text","Date", "DateTime", "Number", "URL"]:
                            temp["python_type_value_list"] = [basestring,unicode,str]
                        elif r in ["Integer"]:
                            temp["python_type_value_list"] = [int]
                        elif r in ["Float"]:
                            temp["python_type_value_list"] = [float]
                        else:
                            temp["cns_range_list"] = [ r ]

                        self.index_validate_range[p] = temp

    def _build_index_domain(self, available_schema_list):
        #reset
        self.index_validate_domain = collections.defaultdict( list )

        #init system property
        self.index_validate_domain ["@id"] = ["Thing","Link", "CnsMetadata"]
        self.index_validate_domain ["@type"] = ["Thing","Link", "CnsMetadata","CnsDataStructure"]
        self.index_validate_domain ["@context"] = ["CnsOntology"]
        self.index_validate_domain ["@graph"] = ["CnsOntology"]
        self.index_validate_domain ["rdfs:domain"] = ["rdf:Property"]
        self.index_validate_domain ["rdfs:range"] = ["rdf:Property"]
        self.index_validate_domain ["rdfs:subClassOf"] = ["rdfs:Class"]
        self.index_validate_domain ["rdfs:subPropertyOf"] = ["rdf:Property"]

        #build
        for schema in available_schema_list:
            for cns_item in schema.definition.values():
                #should not define system properties
                if cns_item["name"] in ["@id", "@type"]:
                    assert False, json4debug(cns_item)

                # regular properties only
                if "rdf:Property" in cns_item["@type"] and "rdfs:domain" in cns_item:
                    p = cns_item["name"]
                    d = cns_item["rdfs:domain"]
                    #assert type(r) == list
                    if isinstance(d, list):
                        self.index_validate_domain[p].extend(d)
                    else:
                        self.index_validate_domain[p].append(d)

                    # special hack
                    if d in ["Top"]:
                        self.index_validate_domain[p].extend(["Thing","CnsLink", "CnsMetadata", "CnsDataStructure"])


        # dedup
        for p in self.index_validate_domain:
            self.index_validate_domain[p] = sorted(set(self.index_validate_domain[p]))

    def _build_index_template(self, available_schema_list):
        #reset
        self.index_validate_template = collections.defaultdict(list)

        #build
        for schema in available_schema_list:
            for template in schema.metadata["template"]:
                # clean min/max cardinality

                p = "minCardinality"
                if template[p] == "":
                    template[p] = 0
                else:
                    template[p] = int(template[p])
                assert template[p] in [0,1], template

                p = "maxCardinality"
                if p not in template:
                    pass
                elif type(template[p]) in [float, int]:
                    template[p] = int(template[p])
                    assert template[p] == 1, template
                elif len(template[p]) == 0:
                    del template[p]
                    pass
                else:
                    assert False, template

                #build index for validation
                template_validation = copy.deepcopy(template)
                p = "propertyRange"
                if template.get(p):
                    template_validation[p] = gen_range_validation_config( template.get(p) , self )
                else:
                    #use range specified in property definition
                    property_definition = self.get_definition_by_alias(template["refProperty"])
                    assert property_definition
                    template_validation[p] = gen_range_validation_config( property_definition["rdfs:range"]  , self)


                d = template["refClass"]
                self.index_validate_template[d].append( template_validation )

                #unfold in/out tempalte for simple CnsLink promoted from relation
                # if template_validation[p]["cns_range_entity"]:
                #     refClass = template_validation["refProperty"]
                #     template_old = None
                #     for temp self.index_validate_template[refClass]:
                #         if temp["refProperty"] == "in"
                #             template_old = temp
                #             break
                #
                #     if template_old:
                #         template_old["cns_range_entity"].append(d)
                #     else:
                #         template_new = {}
                #         template_new["propertyRange"]= {"text": d, "python_type_value_list":[], "cns_range_entity":[d], "cns_range_datastructure":[]}
                #         template_new["refProperty"] = "in"
                #         template_new["refClass"] = refClass
                #         self.index_validate_template[refClass].append( template_new)
                #
                #     template_old = None
                #     for temp self.index_validate_template[refClass]:
                #         if temp["refProperty"] == "out"
                #             template_old = temp
                #             break
                #
                #     if template_old:
                #         template_old["cns_range_entity"].extend(template_validation["cns_range_entity"])
                #     else:
                #         template_new = {}
                #         template_new["propertyRange"]= template_validation["propertyRange"]
                #         template_new["refProperty"]="out"
                #         template_new["refClass"] = refClass
                #         self.index_validate_template[refClass].append( template_new)

    def _build_index_property_alias(self, available_schema_list):
        self.index_property_alias = {}

        map_name_alias = collections.defaultdict(set)

        #build alias
        for schema in available_schema_list:
            for cns_item in schema.definition.values():
                if "rdf:Property" in cns_item["@type"]:
                    plist = gen_plist( cns_item )
                    alias =  plist["name"]
                    map_name_alias[alias].add( plist["name"] )
                    for alias in plist["alternateName"]:
                        map_name_alias[alias].add( plist["name"] )

        #validate
        for alias, v in map_name_alias.items():
#            logging.info(alias)
            assert len(v) == 1, (alias, list(v))
            self.index_property_alias[alias] = list(v)[0]

    def _build_index_definition_alias(self, available_schema_list):
        self.index_definition_alias = {}

        map_name_item = collections.defaultdict(list)

        #collect alias from definition
        for schema in available_schema_list:
            for cns_item in schema.definition.values():
                if "cns_schemaorg" == schema.metadata["name"]:
                    if cns_item["@id"] in available_schema_list[0].definition:
                        # if definition is defined in cns_top, then
                        # skip schemaorg's defintion
                        continue

                plist = gen_plist( cns_item )
                names = [ plist["name"] ]
                names.extend( plist["alternateName"] )
                for alias in set(names):
                    map_name_item[alias].append( cns_item )


        #validate
        for alias, v in map_name_item.items():
            if len(v) > 1:
                logging.info(alias)
                logging.info(json4debug(v))
                assert False
                #assert len(v) == 1, alias
            self.index_definition_alias[alias] = v[0]

        #if self.metadata['name'] == "cns_fund_public":
        #    logging.info([x.metadata["name"] for x in available_schema_list])
        #    assert "Company" in self.index_definition_alias

        #add system
        self.index_definition_alias["rdf:Property"] = {"name":"Property"}
        self.index_definition_alias["rdfs:Class"] = {"name":"Class"}
        self.index_definition_alias["rdfs:domain"] = {"name":"domain"}
        self.index_definition_alias["rdfs:range"] = {"name":"range"}
        self.index_definition_alias["rdfs:subClassOf"] = {"name":"subClassOf"}
        self.index_definition_alias["rdfs:subPropertyOf"] = {"name":"subPropertyOf"}
        #self.index_definition_alias["@graph"] = {"name":"subPropertyOf"}
        #self.index_definition_alias["@context"] = {"name":"subPropertyOf"}




    def import_jsonld(self, filename=None, preloaded_schema_list={}):
        #reset data
        jsonld = file2json(filename)
        return self.import_jsonld_content(jsonld, preloaded_schema_list)

    def import_jsonld_content(self, jsonld, preloaded_schema_list={}):
        #load
        assert jsonld["@context"]["@vocab"] == "http://cnschema.org/"

        for p in jsonld:
            if p.startswith("@"):
                pass
            elif p in ["template"]:
                for v in jsonld[p]:
                    self.add_metadata(p, v)
            else:
                self.add_metadata(p, jsonld[p])



        for definition in jsonld["@graph"]:
            self.set_definition(definition)

        self.build(preloaded_schema_list)


    def export_jsonld(self, filename=None):
        xid = "http://cnschema.org/schema/{}".format(self.metadata["name"] )

        # assign values
        jsonld = {  "@context": {
                        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                        "@vocab": "http://cnschema.org/"
                    },
                    "@id": xid,
                    "@type": ["CnsOntology", "Thing"],
                    "name": self.metadata["name"] ,
                    "@graph": self.definition.values() }

        for p in self.metadata:
            if p in ["changelog", "template"]:
                jsonld[p] = self.metadata[p]
            elif p in ["name"]:
                pass
            else:
                jsonld[p] = self.metadata[p]

        #sort, achieve cannonical representation (sorted)
        for p,v in jsonld.items():
            if p in ["@id","@type","import"]:
                continue

            if type(v) == list:
                # logging.info(json4debug(v))
                jsonld[p] = sorted(v, key=lambda x: [x.get("@id",""), x.get("name","")] )

        #save to file
        if filename:
            json2file(jsonld,filename)

        return jsonld

    def export_debug(self, filename=None):
        output = {
            u"index_property_alias_属性名称映射表": self.index_property_alias,
            u"index_definition_alias_定义名称映射表": self.index_definition_alias,
            u"index_validate_template": self.index_validate_template,
            u"index_validate_domain": self.index_validate_domain,
            #u"index_validate_range": self.index_validate_range,
            u"index_inheritance": self.index_inheritance,
        }

        #save to file
        if filename:
            json2file(output,filename)

        return output


def task_import_schema(args):
    logging.info("enter")
    filename = args["input_file"]
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(filename)
    logging.info(filename)

    #validate if we can reproduce the same jsonld based on input
    jsonld_input = file2json(filename)

    xdebug_file = os.path.join(args["debug_dir"],os.path.basename(args["input_file"]))
    filename_debug = xdebug_file+u".debug-jsonld.json"
    jsonld_output = loaded_schema.export_jsonld(filename_debug)

    assert len(jsonld_input) == len(jsonld_output)
    x = json4debug(jsonld_input).splitlines(1)
    y = json4debug(jsonld_output).splitlines(1)
    diff = unified_diff(x,y)
    logging.info( ''.join(diff) )
    for idx, line in enumerate(x):
        if x[idx] != y[idx]:
            logging.info(json4debug([idx, x[idx],y[idx]]) )
            break

    filename_debug = xdebug_file+u".debug-memory.json"
    jsonld_output = loaded_schema.export_debug(filename_debug)


def preload_schema(args=None):
    logging.info("enter")
    dir_schema = args.get("dir_schema")
    if not dir_schema:
        dir_schema="cnschema"

    schema_name_list = args.get("schema_name_list")
    if schema_name_list is not None:
        schema_name_list = [x.strip() for x in schema_name_list.split(",") if x.strip()]
    else:
        schema_name_list = ["cns_top","cns_place","cns_person","cns_organization"]

    preloaded_schema_list = {}
    for schema_name in schema_name_list:
        filename = u"{}/{}.jsonld".format(dir_schema, schema_name)
        assert os.path.exists(filename), filename

        loaded_schema = CnsSchema()
        loaded_schema.import_jsonld(filename, preloaded_schema_list)
        preloaded_schema_list[schema_name] = loaded_schema
        logging.info("loaded {}".format(schema_name))

    logging.info(len(preloaded_schema_list))
    return preloaded_schema_list

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--dir_schema': 'input schema',
        '--debug_dir': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    # task 1: import jsonld (and is loaded completely)
    python kgtool/cns_model.py task_import_schema --input_file=schema/cns_top.jsonld --debug_dir=local/debug --dir_schema=schema
    python kgtool/cns_model.py task_import_schema --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/debug --dir_schema=schema
    python kgtool/cns_model.py task_import_schema --input_file=schema/cns_organization.jsonld --debug_dir=local/debug --dir_schema=schema

    python kgtool/cns_model.py task_import_schema --input_file=local/cns_fund_public.jsonld --debug_dir=local/debug --dir_schema=schema

"""
