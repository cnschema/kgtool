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
VERSION = 'v20180519'
CONTEXTS = [os.path.basename(__file__), VERSION]

from core import *  # noqa

"""
It stores cnSchema data:
 * definition: defintion of a class, property, or a constant
 * metadata: list of cardinality restriction， changelog

It offers the following functions:
* cns loader： load a collection of cnSchema,
   * load class/property addDefinition
   * load cardinality restriction metadata
   * load version metadata
   * validate unique name/alias of class/property,
* cns converter
* cnsValidate : validate integrity constraints
   * class-property cardinality
   * class-property association
   * property range
"""

def _report(report, bug):
    msg = json.dumps(bug, ensure_ascii=False, sort_keys=True)
    report["bugs"].append(bug)
    return msg


class CnsSchema:
    def __init__(self):
        # Schema raw data: metadata information, key => value
        # version
        # cardinality
        self.metadata = collections.defaultdict(list)

        # Schema raw data: concept definition,  @id => entity
        self.definition = collections.defaultdict(dict)

        # schema raw data: 引用相关Schema
        self.importSchema = []


        #index: 属性名称映射表  property alias => property standard name
        self.indexPropertyAlias = {}

        #index: 定义名称映射表  defintion alias => definition（property/class）
        self.indexDefinitionAlias = {}

        #index: VALIDATION  class => cardinality Object
        self.indexValidateCardinality = collections.defaultdict( dict )

        #index: VALIDATION  property => expected types
        self.indexValidateDomain = collections.defaultdict( list )

        #index: VALIDATION  property =>  range
        self.indexValidateRange = collections.defaultdict( dict )

    def initReport(self):
        return  {"bugs":[],"stats":collections.Counter()}

    def cnsValidateRecursive(self, cnsTree, report):
        if type(cnsTree) == list:
            for cnsItem in cnsTree:
                self.cnsValidateRecursive(cnsItem, report)
        elif type(cnsTree) == dict:
            self.cnsValidate(cnsTree, report)
            self.cnsValidateRecursive(cnsTree.values(), report)
        else:
            # do not validate
            pass

    def cnsValidate(self, cnsItem, report):
        """
            validate the following
            * cardinality restriction  (class-property binding)

            * range of property
        """
        report["stats"]["items_validated"] += 1

        if not self._validateSystem(cnsItem, report):
            return report

        self._validateCardinality(cnsItem, report)

        self._validateRange(cnsItem, report)

        self._validateDomain(cnsItem, report)

        return report

    def _validateSystem(self, cnsItem, report):
        types = cnsItem.get("@type")
        if "@vocab" in cnsItem:
            bug = {
                "category": "info_validate_system",
                "text": "skip validating system @vocab",
            }
            logging.info(_report(report, bug))
            return False

        if not types:
            bug = {
                "category": "warn_validate_system",
                "text": "item missing @type",
                "item": cnsItem
            }
            logging.warn(_report(report, bug))

            return False

        return True

    def _validateRange(self, cnsItem, report):
        #TODO only validate non object range for now

        TEXT_PROP = [""]
        for p in cnsItem:
            if p in ["@context"]:
                #skip this range check
                bug = {
                    "category": "info_validate_range",
                    "text": "skip validating range @vocab",
                    #"item": cnsItem
                }
                logging.warn(_report(report, bug))
                continue

            rangeExpect = self.indexValidateRange.get(p)
            if not rangeExpect:
                bug = {
                    "category": "warn_validate_range",
                    "text": "range not specified in schema",
                    "property": p
                }
                logging.warn(_report(report, bug))
                continue

            for v in json_get_list(cnsItem, p):
                if "pythonTypeValue" in rangeExpect:
                    rangeActual = type(v)
                    if rangeActual in rangeExpect["pythonTypeValue"]:
                        # this case is fine
                        pass
                    else:
                        bug = {
                            "category": "warn_validate_range",
                            "text": "range value datatype mismatch",
                            "property": p,
                            "expected" : rangeExpect["text"],
                            "actual" : str(rangeActual),
                        }
                        logging.warn(_report(report, bug))
                else:
                    if type(v)== dict:
                        rangeActual = v.get("@type",[])
                        if set(rangeExpect["cnsRange"]).intersection(rangeActual):
                            # this case is fine
                            pass
                        else:
                            bug = {
                                "category": "warn_validate_range",
                                "text": "range object missing types",
                                "property": p,
                                "expected" : rangeExpect["cnsRange"],
                                "actual" : rangeActual,
                            }
                            logging.warn(_report(report, bug))
                    else:
                        bug = {
                            "category": "warn_validate_range",
                            "text": "range value should be object",
                            "property": p,
                            "expected" : rangeExpect["cnsRange"],
                            "item" : v,
                        }
                        logging.warn(_report(report, bug))


    def _validateDomain(self, cnsItem, report):
        # cardinality validation
        validated_property = set()
        for p in cnsItem:
            domainExpected = self.indexValidateDomain.get(p)
            if domainExpected == None:
                bug = {
                    "category": "warn_validate_domain",
                    "text": "domain not specified in schema",
                    "property": p
                }
                logging.warn(_report(report, bug))
                continue



            domainActual = cnsItem.get("@type",[])
            for domain in domainActual:
                if not self.indexDefinitionAlias.get(domain):
                    bug = {
                        "category": "warn_validate_definition",
                        "text": "class not defined in schema",
                        "class": domain
                    }
                    logging.warn(_report(report, bug))

            if not domainActual:
                bug = {
                    "category": "warn_validate_domain",
                    "text": "domain not specified",
                    "property": p,
                    "item": cnsItem
                }
                logging.warn(_report(report, bug))
            elif set(domainExpected).intersection(domainActual):
                # this case is fine
                pass
            else:
                bug = {
                    "category": "warn_validate_domain",
                    "text": "domain unexpected",
                    "property": p,
                    "expected": domainExpected,
                    "actual": domainActual
                }
                logging.warn(_report(report, bug))

    def _validateCardinality(self, cnsItem, report):
        # cardinality validation
        validated_property = set()
        for xtype in cnsItem["@type"]:
            for cardinality in self.indexValidateCardinality[xtype]:
                p = cardinality["propertyName"]
                if p in validated_property:
                    continue
                else:
                    validated_property.add(p)

                cardAcual = len(json_get_list(cnsItem, p))

                if cardAcual < cardinality["minCardinality"]:
                    bug = {
                        "category": "warn_validate_cardinality",
                        "text": "minCardinality",
                        "property": p,
                        "expected": cardinality["minCardinality"],
                        "actual": cardAcual
                    }
                    logging.warn(_report(report, bug))


                if "maxCardinality" in cardinality:
                    if cardAcual > cardinality["maxCardinality"]:
                        bug = {
                            "category": "warn_validate_cardinality",
                            "text": "maxCardinality",
                            "property": p,
                            "expected": cardinality["maxCardinality"],
                            "actual": cardAcual
                        }
                        logging.warn(_report(report, bug))




    def cnsConvert(self, item, types, primaryKeys, report = None):
        """
            property_alias  => property_name
            create @id
            assert @type
        """
        if report == None:
            report = self.initReport()

        assert types
        if primaryKeys:
            assert type(primaryKeys) == list

        if "@id" in item:
            pass
        else:
            assert primaryKeys

        cnsItem = {
            "@type": types,
            "@id" : item.get("@id", any2sha1( primaryKeys ))
        }

        for p,v in item.items():
            px = self.indexPropertyAlias.get(p)
            if px:
                cnsItem[px] = v
            else:
                bug = {
                    "category": "warn_convert_cns",
                    "text": "property not defined in schema",
                    "property": p
                }

                logging.warn(_report(report, bug))


        # add alternateName when it is not set
        p = "alternateName"
        if not p in cnsItem and "name" in cnsItem:
            cnsItem[p] = [ cnsItem["name"] ]

        return cnsItem

    def addDefinition(self, item):
        self.definition[item["@id"]]  = item

    def build(self):
        schemaList = [self]
        #schemaList.extend( self.importSchema )

        self._buildindexPropertyAlias(schemaList)
        self._buildindexDefinitionAlias(schemaList)
        self._buildIndexRange(schemaList)
        self._buildIndexCardinality(schemaList)
        self._buildIndexDomain(schemaList)

        self._validateSchema()

        return self._stat()

    def _validateSchema(self):
        for cardinality in self.metadata["cardinality"]:
            cls = self.indexDefinitionAlias.get( cardinality["className"] )
            #logging.info(json4debug(sorted(self.indexDefinitionAlias.keys())))
            assert cls, json4debug(cardinality)
            assert cls["name"] == cardinality["className"]
            assert cls["@type"][0] == "rdfs:Class"

            prop = self.indexDefinitionAlias.get( cardinality["propertyName"] )
            assert prop, json4debug(cardinality)
            assert prop["name"] == cardinality["propertyName"]
            assert prop["@type"][0] == "rdf:Property"

    def _stat(self):
        stat = collections.Counter()
        for cnsItem in self.definition.values():
            if "rdf:Property" in cnsItem["@type"]:
                stat["cntProperty"] +=1
            elif  "rdfs:Class" in cnsItem["@type"]:
                stat["cntClass"] +=1

        stat["cntCardinality"] += len(self.metadata["cardinality"])

        ret = {
            "name" : self.metadata["name"],
            "stat" : stat
        }
        logging.info(json4debug( ret ))
        return ret

    def _buildIndexRange(self, schemaList):
        #reset
        self.indexValidateRange = {}

        #init system property
        self.indexValidateRange["@id"] = {"text": "UUID", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange["@type"] = {"text": "Text", "pythonTypeValue":[basestring,unicode,str]}
#        self.indexValidateRange ["@context"] = {"text": "SYS", "cnsRange": []}
        self.indexValidateRange ["@graph"] = {"text": "SYS", "cnsRange": ["Thing"]}
        self.indexValidateRange ["rdfs:domain"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange ["rdfs:range"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange["rdfs:subClassOf"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange["rdfs:subPropertyOf"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}

        #build
        for schema in schemaList:
            for cnsItem in schema.definition.values():
                if cnsItem["name"] in ["@id", "@type"]:
                    assert False, json4debug(cnsItem)

                if "rdf:Property" in cnsItem["@type"]:
                    p = cnsItem["name"]
                    r = cnsItem["rdfs:range"]
                    #assert type(r) == list
                    if not p in self.indexValidateRange:
                        temp = {"text": r}
                        if r in ["Text","Date", "DateTime", "Number", "URL"]:
                            temp["pythonTypeValue"] = [basestring,unicode,str]
                        elif r in ["Integer"]:
                            temp["pythonTypeValue"] = [int]
                        elif r in ["Float"]:
                            temp["pythonTypeValue"] = [float]
                        else:
                            temp["cnsRange"] = [ r ]

                        self.indexValidateRange[p] = temp

    def _buildIndexDomain(self, schemaList):
        #reset
        self.indexValidateDomain = collections.defaultdict( list )

        #init system property
        self.indexValidateDomain ["@id"] = ["Thing","Link", "CardinalityConstraint"]
        self.indexValidateDomain ["@type"] = ["Thing","Link","DataStructure"]
        self.indexValidateDomain ["@context"] = ["Ontology"]
        self.indexValidateDomain ["@graph"] = ["Ontology"]
        self.indexValidateDomain ["rdfs:domain"] = ["rdf:Property"]
        self.indexValidateDomain ["rdfs:range"] = ["rdf:Property"]
        self.indexValidateDomain["rdfs:subClassOf"] = ["rdfs:Class"]
        self.indexValidateDomain["rdfs:subPropertyOf"] = ["rdf:Property"]

        #build
        for schema in schemaList:
            for cnsItem in schema.definition.values():
                #should not define system properties
                if cnsItem["name"] in ["@id", "@type"]:
                    assert False, json4debug(cnsItem)

                # regular properties only
                if "rdf:Property" in cnsItem["@type"]:
                    p = cnsItem["name"]
                    d = cnsItem["rdfs:domain"]
                    #assert type(r) == list
                    self.indexValidateDomain[p].append(d)

                    # special hack
                    if d in ["Top"]:
                        self.indexValidateDomain[p].extend(["Thing", "Link", "DataStructure"])


        # dedup
        for p in self.indexValidateDomain:
            self.indexValidateDomain[p] = sorted(set(self.indexValidateDomain[p]))

    def _buildIndexCardinality(self, schemaList):
        #reset
        self.indexValidateCardinality = collections.defaultdict(list)

        #build
        for schema in schemaList:
            for cardinality in schema.metadata["cardinality"]:
                d = cardinality["className"]
                temp = cardinality["category"].split("_")
                cardinality["minCardinality"] = int(temp[0])
                if len(temp)==2:
                    if temp[1] in ["n"]:
                        pass
                    else:
                        cardinality["maxCardinality"] = int(temp[1])
                self.indexValidateCardinality[d].append( cardinality )

    def _buildindexPropertyAlias(self, schemaList):
        self.indexPropertyAlias = {}

        mapNameAlias = collections.defaultdict(set)

        #build alias
        for schema in schemaList:
            for cnsItem in schema.definition.values():
                if "rdf:Property" in cnsItem["@type"]:
                    plist = self._extractPlist( cnsItem )
                    names = [ plist["name"] ]
                    names.extend( plist["alternateName"] )
                    for alias in set(names):
                        mapNameAlias[alias].add( plist["name"] )

        #validate
        for alias, v in mapNameAlias.items():
            temp = json4debug(list(v))
            assert len(v) == 1, temp
            self.indexPropertyAlias[alias] = list(v)[0]

    def _buildindexDefinitionAlias(self, schemaList):
        self.indexDefinitionAlias = {}

        mapNameItem = collections.defaultdict(list)

        #collect alias
        for schema in schemaList:
            for cnsItem in schema.definition.values():
                plist = self._extractPlist( cnsItem )
                names = [ plist["name"] ]
                names.extend( plist["alternateName"] )
                for alias in set(names):
                    mapNameItem[alias].append( cnsItem )

        #validate
        for alias, v in mapNameItem.items():
            if len(v) > 1:
                logging.info(alias)
                logging.info(json4debug(v))
                assert False
                #assert len(v) == 1, alias
            self.indexDefinitionAlias[alias] = v[0]

        #add system
        self.indexDefinitionAlias["rdf:Property"] = {"name":"Property"}
        self.indexDefinitionAlias["rdfs:Class"] = {"name":"Class"}
        self.indexDefinitionAlias["rdfs:domain"] = {"name":"domain"}
        self.indexDefinitionAlias["rdfs:range"] = {"name":"range"}
        self.indexDefinitionAlias["rdfs:subClassOf"] = {"name":"subClassOf"}
        self.indexDefinitionAlias["rdfs:subPropertyOf"] = {"name":"subPropertyOf"}
        #self.indexDefinitionAlias["@graph"] = {"name":"subPropertyOf"}
        #self.indexDefinitionAlias["@context"] = {"name":"subPropertyOf"}

    def _extractPlist(self, cnsItem):
        #if 'rdfs:domain' in cnsItem:
        #    domains = parseListValue(cnsItem["rdfs:domain"])
        #else:
        #    assert False, cnsItem

        plist_meta = [ {"name":"name", "alternateName":["propertyName"]},
                       {"name":"alternateName", "alternateName":["propertyAlternateName"]}]
        plist = json_dict_copy(cnsItem, plist_meta)
        assert plist["name"], cnsItem

        #for debug purpose
        #if 29 == plist["name"]:
        #    assert False, cnsItem

        plist["alternateName"] = parseListValue( plist.get("alternateName", []) )
        for p,v in cnsItem.items():
            if p == "name":
                continue

            if p.startswith("name"):
                if v not in plist["alternateName"]:
                    plist["alternateName"].append( v )

        return plist


    def addMetadata(self, group, item):
        if group in ["version", "cardinality"]:
            self.metadata[group].append(item)
        else:
            self.metadata[group] = item

    def exportDebug(self, filename=None):
        output = {
            u"indexPropertyAlias_属性别名": self.indexPropertyAlias
        }

        #save to file
        if filename:
            json2file(output,filename)

        return output


    def exportJsonLd(self, filename=None):
        xid = "http://cnschema.org/schema/{}".format(self.metadata["name"] )

        # assign values
        jsonld = {  "@context": {
                        "@vocab": "http://cnschema.org/"
                    },
                    "@id": xid,
                    "@type": ["Ontology", "Thing"],
                    "name": self.metadata["name"] ,
                    "@graph": self.definition.values() }

        for p in self.metadata:
            if p in ["changelog", "cardinality"]:
                jsonld[p] = self.metadata[p]
            else:
                assert p in ["name"], p

        #sort, achieve cannonical representation (sorted)
        for p,v in jsonld.items():
            if p in ["@id","@type"]:
                continue

            if type(v) == list:
                jsonld[p] = sorted(v, key=lambda x: [x.get("@id",""), x.get("name","")] )

        #save to file
        if filename:
            json2file(jsonld,filename)

        return jsonld

    def importJsonLd(self, filename=None):
        #reset data

        #load
        jsonld = file2json(filename)
        assert jsonld["@context"]["@vocab"] == "http://cnschema.org/"
        for p in ["name"]:
            self.addMetadata(p, jsonld[p])

        for p in ["cardinality", "changelog"]:
            for v in jsonld[p]:
                self.addMetadata(p, v)


        for definition in jsonld["@graph"]:
            self.addDefinition(definition)

        self.build()

def task_importJsonld(args):
    logging.info( "called task_excel2jsonld" )
    filename = args["input_file"]
    cnsSchema = CnsSchema()
    cnsSchema.importJsonLd(filename)

    #validate if we can reproduce the same jsonld based on input
    jsonld_input = file2json(filename)

    xdebug_file = os.path.join(args["debug_dir"],os.path.basename(args["input_file"]))
    filename_debug = xdebug_file+u".debug-2"
    jsonld_output = cnsSchema.exportJsonLd(filename_debug)

    assert len(jsonld_input) == len(jsonld_output)
    x = json4debug(jsonld_input).split("\n")
    y = json4debug(jsonld_output).split("\n")
    for idx, line in enumerate(x):
        if x[idx] != y[idx]:
            logging.info(json4debug([idx, x[idx],y[idx]]) )
            break

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
    # task 1: import jsonld (and is loaded completely)
    python kgtool/cns_schema.py task_importJsonld --input_file=schema/cns-thing-18q3.jsonld --debug_dir=local/

    # task 2: convert

    # task 3: validate

"""
