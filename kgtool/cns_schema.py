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
from kgtool.stats import stat_kg_report_per_item

# global constants
VERSION = 'v20180724'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
It stores cnSchema data:
 * definition: defintion of a class, property, or a constant
 * metadata: list of template restriction， changelog

It offers the following functions:
* cns loader: load a collection of cnSchema,
   * load class/property set_definition
   * load template restriction metadata
   * load version metadata
   * validate unique name/alias of class/property,
* cnsConvert: convert non-cnSchema JSON into cnsItem using loaded_schema properties
* run_validate: validate integrity constraints imposed by template and property definition
   * class-property binding
   * property domain
   * property range
* run_graphviz: generate a graphviz dot format of a schema
"""
def lambda_key_cns_link(cns_item):
    assert cns_item["@type"]
    assert isinstance(cns_item["@type"], list)
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
        return any2sha256(lambda_key_cns_link(cns_item))
    else:
        raise Exception("unexpected situation")  # unexpected situation

def write_report(report, bug):
    key = ur" | ".join([bug["category"], bug["text"], bug.get("class",""), bug.get("property","")])
    report["stats"][key]+=1
    if key not in report["bugs_sample"]:
        report["bugs_sample"][key] = copy.deepcopy(bug)

    if report.get("flag_detail"):
        msg = json.dumps(bug, ensure_ascii=False, sort_keys=True)
        report["bugs"].append(bug)
        logging.info(msg)


class CnsSchema:
    def __init__(self):
        # Schema raw data: metadata information, key => value
        # version
        # template
        self.metadata = collections.defaultdict(list)

        # Schema raw data: concept definition,  @id => entity
        self.definition = collections.defaultdict(dict)

        # schema raw data: 引用相关Schema
        self.imported_schema_list = []


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

    def init_report(self):
        return  {"bugs":[], "bugs_sample":{},"stats":collections.Counter(), "flag_detail": False}

    def run_validateRecursive(self, cnsTree, report):
        if type(cnsTree) == list:
            for cnsItem in cnsTree:
                self.run_validateRecursive(cnsItem, report)
        elif type(cnsTree) == dict:
            self.run_validate(cnsTree, report)
            self.run_validateRecursive(cnsTree.values(), report)
        else:
            # do not validate
            pass



    def run_validate(self, cnsItem, report):
        """
            validate the following
            * template restriction  (class-property binding)

            * range of property
        """
        report["stats"]["items_validated"] += 1

        if not self._validateSystem(cnsItem, report):
            return report

        self._validateClass(cnsItem, report)

        self._validateTemplate(cnsItem, report)

        self._validateRange(cnsItem, report)

        self._validateDomain(cnsItem, report)

        return report

    def _validateClass(self, cnsItem, report):
        """
            if type is defined in schema
        """
        for xtype in cnsItem["@type"]:
            has_type = False
            for schema in self.loaded_schema_list:
                type_definition = schema.index_definition_alias.get(xtype)
                if type_definition:
                    has_type =True
                    break

            if not has_type:
                bug = {
                    "category": "info_validate_class",
                    "text": "class not defined",
                    "class" : xtype,
                    #"item": cnsItem
                }
                write_report(report, bug)



    def _validateSystem(self, cnsItem, report):
        types = cnsItem.get("@type")
        if "@vocab" in cnsItem:
            bug = {
                "category": "info_validate_system",
                "text": "skip validating system @vocab",
            }
            write_report(report, bug)
            return False

        if not types:
            bug = {
                "category": "warn_validate_system",
                "text": "item missing @type",
                "item": cnsItem
            }
            write_report(report, bug)
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
                write_report(report, bug)
                continue

            rangeExpect = self.index_validate_range.get(p)
            if not rangeExpect:
                bug = {
                    "category": "warn_validate_range",
                    "text": "range not specified in schema",
                    "property": p
                }
                write_report(report, bug)
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
                        write_report(report, bug)
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
                            write_report(report, bug)
                    else:
                        bug = {
                            "category": "warn_validate_range",
                            "text": "range value should be object",
                            "property": p,
                            "expected" : rangeExpect["cnsRange"],
                            "actual" : v,
                            #"item" : v,
                        }
                        write_report(report, bug)


    def _validateDomain(self, cnsItem, report):
        # template validation
        validated_property = set()
        for p in cnsItem:
            domainExpected = self.index_validate_domain.get(p)
            if domainExpected == None:
                bug = {
                    "category": "warn_validate_domain",
                    "text": "domain not specified in schema",
                    "property": p
                }
                write_report(report, bug)
                continue



            domainActual = cnsItem.get("@type",[])
            for domain in domainActual:
                if not self.index_definition_alias.get(domain):
                    bug = {
                        "category": "warn_validate_definition",
                        "text": "class not defined in schema",
                        "class": domain
                    }
                    write_report(report, bug)

            if not domainActual:
                bug = {
                    "category": "warn_validate_domain",
                    "text": "domain not specified",
                    "property": p,
                    "item": cnsItem
                }
                write_report(report, bug)
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
                write_report(report, bug)

    def _validateTemplate(self, cnsItem, report):
        # template validation
        validated_property = set()
        for xtype in cnsItem["@type"]:
            for template in self.index_validate_template[xtype]:
                p = template["refProperty"]
                if p in validated_property:
                    continue
                else:
                    validated_property.add(p)

                cardAcual = len(json_get_list(cnsItem, p))

                if cardAcual < template["minCardinality"]:
                    # logging.info(json4debug(template))
                    # logging.info(json4debug(cnsItem))
                    # assert False
                    bug = {
                        "category": "warn_validate_template",
                        "text": "minCardinality",
                        "property": p,
                        "expected": template["minCardinality"],
                        "actual": cardAcual,
                        "item_name": cnsItem.get("name"),
                        "item_value": cnsItem.get(p),
                    }
                    write_report(report, bug)


                if "maxCardinality" in template:
                    if cardAcual > template["maxCardinality"]:
                        bug = {
                            "category": "warn_validate_template",
                            "text": "maxCardinality",
                            "property": p,
                            "expected": template["maxCardinality"],
                            "actual": cardAcual,
                            "item_name": cnsItem.get("name"),
                            "item_value": cnsItem.get(p),
                        }
                        write_report(report, bug)




    def cnsConvert(self, item, types, primary_keys, report = None):
        """
            property_alias  => property_name
            create @id
            assert @type
        """
        assert types
        if primary_keys:
            assert type(primary_keys) == list


        cnsItem = {
            "@type": types,
        }

        for p,v in item.items():
            px = self.index_property_alias.get(p)
            if px:
                cnsItem[px] = v
            else:
                bug = {
                    "category": "warn_convert_cns",
                    "text": "property not defined in schema",
                    "property": p
                }

                if report is not None:
                    write_report(report, bug)


        if item.get("@id"):
            cnsItem["@id"] = item["@id"]

        xid = gen_cns_id(cnsItem, primary_keys)
        cnsItem["@id"] = xid

        return cnsItem

    def set_definition(self, item):
        self.definition[item["@id"]]  = item

    def get_definition(self, xid):
        return self.definition.get(xid)

    def build(self, preloadSchemaList={}):
        def _build_imported_schema_list(schema):
            #handle import
            name = schema.metadata["name"]
            imported_schema_list = []
            importedSchemaName = []
            if name != "cns_top":
                importedSchemaName.append( "cns_top" )

            #logging.info(json4debug(schema.metadata))
            importedSchemaName.extend( json_get_list(schema.metadata, "import") )
            #logging.info(json4debug(schema.metadata["import"]))
            #assert False

            #logging.info(json4debug(importedSchemaName))
            for schemaName in importedSchemaName:
                schema = preloadSchemaList.get(schemaName)
                if not schema:
                    #load schema on demand
                    filename = u"../schema/{}.jsonld".format(schemaName)
                    filename = file2abspath(filename)
                    logging.info("import schema "+ filename)
                    schema = CnsSchema()
                    schema.import_jsonld(filename, preloadSchemaList)

                assert schema, schemaName
                imported_schema_list.append( schema )
                logging.info("importing {}".format(schemaName))
            return imported_schema_list

        available_schema_list = []
        #available_schema_list.extend( self.imported_schema_list )
        available_schema_list.extend(_build_imported_schema_list(self))
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
        self._build_index_range(available_schema_list)
        self._build_index_template(available_schema_list)
        self._build_index_domain(available_schema_list)

        #logging.info([x.metadata["name"] for x in available_schema_list])
        self._validateSchema()

        return self._stat()

    def _validateSchema(self):
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

    def _build_index_range(self, available_schema_list):
        #reset
        self.index_validate_range = {}

        #init system property
        self.index_validate_range["@id"] = {"text": "UUID", "pythonTypeValue":[basestring,unicode,str]}
        self.index_validate_range["@type"] = {"text": "Text", "pythonTypeValue":[basestring,unicode,str]}
#        self.index_validate_range ["@context"] = {"text": "SYS", "cnsRange": []}
        self.index_validate_range ["@graph"] = {"text": "SYS", "cnsRange": ["CnsMetadata"]}
        self.index_validate_range ["rdfs:domain"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.index_validate_range ["rdfs:range"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.index_validate_range["rdfs:subClassOf"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.index_validate_range["rdfs:subPropertyOf"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}

        #build
        for schema in available_schema_list:
            for cnsItem in schema.definition.values():
                if cnsItem["name"] in ["@id", "@type"]:
                    assert False, json4debug(cnsItem)

                if "rdf:Property" in cnsItem["@type"] and "rdfs:range" in cnsItem:
                    #logging.info(json4debug(cnsItem))
                    p = cnsItem["name"]
                    r = cnsItem["rdfs:range"]
                    #assert type(r) == list
                    if not p in self.index_validate_range:
                        temp = {"text": r}
                        if r in ["Text","Date", "DateTime", "Number", "URL"]:
                            temp["pythonTypeValue"] = [basestring,unicode,str]
                        elif r in ["Integer"]:
                            temp["pythonTypeValue"] = [int]
                        elif r in ["Float"]:
                            temp["pythonTypeValue"] = [float]
                        else:
                            temp["cnsRange"] = [ r ]

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
            for cnsItem in schema.definition.values():
                #should not define system properties
                if cnsItem["name"] in ["@id", "@type"]:
                    assert False, json4debug(cnsItem)

                # regular properties only
                if "rdf:Property" in cnsItem["@type"] and "rdfs:domain" in cnsItem:
                    p = cnsItem["name"]
                    d = cnsItem["rdfs:domain"]
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
                d = template["refClass"]

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

                self.index_validate_template[d].append( template )

    def _build_index_property_alias(self, available_schema_list):
        self.index_property_alias = {}

        map_name_alias = collections.defaultdict(set)

        #build alias
        for schema in available_schema_list:
            for cnsItem in schema.definition.values():
                if "rdf:Property" in cnsItem["@type"]:
                    plist = self._extractPlist( cnsItem )
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
            for cnsItem in schema.definition.values():
                if "cns_schemaorg" == schema.metadata["name"]:
                    if cnsItem["@id"] in available_schema_list[0].definition:
                        # if definition is defined in cns_top, then
                        # skip schemaorg's defintion
                        continue

                plist = self._extractPlist( cnsItem )
                names = [ plist["name"] ]
                names.extend( plist["alternateName"] )
                for alias in set(names):
                    map_name_item[alias].append( cnsItem )


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

    def _extractPlist(self, cnsItem):
        #if 'rdfs:domain' in cnsItem:
        #    domains = parseListValue(cnsItem["rdfs:domain"])
        #else:
        #    assert False, cnsItem

        plist_meta = [ {"name":"name", "alternateName":["refProperty"]},
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

            name = None
            if p.startswith("name"):
                name = v
            elif p.startswith("propertyName"):
                name = v
            if name and name not in plist["alternateName"]:
                plist["alternateName"].append( name )

        return plist


    def add_metadata(self, group, item):
        if group in ["version", "template"]:
            self.metadata[group].append(item)
        elif group in [ "import"]:
            if type(item) == list:
                self.metadata[group].extend(item)
            else:
                self.metadata[group].append(item)
        else:
            self.metadata[group] = item

    def exportDebug(self, filename=None):
        output = {
            u"index_property_alias_属性别名": self.index_property_alias
        }

        #save to file
        if filename:
            json2file(output,filename)

        return output


    def run_graphviz(self, name):
        def _get_definition_name(definition):
            return u"{}（{}）".format(definition["name"], definition["nameZh"])

        def _add_graphviz_node(definition, graph):
            if definition is None:
                logging.warn("empty definition")
                return

            #logging.info(definition)
            #if definition["name"] == "city":
            #    logging.info(definition)
            #    assert False

            if "rdf:Property" in definition["@type"]:
                p = "property"
            elif "CnsLink" in definition.get("rdfs:subClassOf",[]):
                p = "link"
            else:
                p = "class"
            graph["nodeMap"][p].add(_get_definition_name(definition))

        def _add_graphviz_link(link, graph):
            #logging.info(json4debug(link))
            if link["from"]["name"] == "CnsLink" and link.get("relation",{}).get("name") == "Thing":
                logging.info(json4debug(link))
            graph["linkList"].append(link)
            _add_graphviz_node(link["from"], graph)
            _add_graphviz_node(link["to"], graph)
            if link["type"].endswith("domain_range") :
                _add_graphviz_node(link["relation"], graph)
            elif link["type"] == "template_link":
                _add_graphviz_node(link["relation"], graph)
            elif link["type"] in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                pass
            else:
                logging.info(json4debug(link))
                assert False

        def _add_domain_range(definition, graph):
            #domain range relation
            if "rdf:Property" in definition["@type"]:
                if definition.get("rdfs:range") and definition.get("rdfs:domain"):
                    range_class = self.index_definition_alias.get( definition["rdfs:range"] )
                    for domain_ref in definition["rdfs:domain"]:
                        domain_class = self.index_definition_alias.get( domain_ref )
                        if domain_class and range_class:
                            link = {
                                "from": domain_class,
                                "to": range_class,
                                "relation": definition,
                                "type": "property_domain_range"
                            }
                            _add_graphviz_link(link, graph)

        def _addSuperClassProperty(definition, graph):
            #super class/property relation
            for p in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                superList = definition.get(p,[])
                for super in superList:
                    superDefinition = self.index_definition_alias.get(super)
                    if superDefinition:
                        link = {
                            "from": definition,
                            "to": superDefinition,
                            "type": p,
                        }
                        _add_graphviz_link(link, graph)

        def _add_template_domain_range(template, graph, map_link_in_out):
            #logging.info(json4debug(template))
            #assert False


            if not template.get("refClass"):
                return
            if not template.get("refProperty"):
                return

            domain_class = self.index_definition_alias.get( template["refClass"])
            if not domain_class:
                return

            _property_definition = self.index_definition_alias.get(template["refProperty"])
            if not _property_definition:
                return


            range_name = ""
            if template.get("propertyRange"):
                range_name = template["propertyRange"]
                range_class = self.index_definition_alias.get( range_name)
            else:
                range_name = _property_definition["rdfs:range"]
                range_class = self.index_definition_alias.get( range_name )

            # special processing on  [in, out], system property for property graph
            if range_class is None and range_name.endswith("Enum"):
                logging.warn("missing definition for ENUM {}".format(range_name))
                return

            assert range_class, template

            link_name = domain_class["name"]
            if template["refProperty"] in ["in"]:
                map_link_in_out[link_name]["from"] = range_class
                map_link_in_out[link_name]["relation"] = domain_class
                map_link_in_out[link_name]["type"] = "template_link"
            elif template["refProperty"] in ["out"]:
                map_link_in_out[link_name]["to"] = range_class
            else:
                link = {
                    "from": domain_class,
                    "to": range_class,
                    "relation": _property_definition,
                    "type": "template_domain_range"
                }
                _add_graphviz_link(link, graph)

        def _filter_compact(graph):
            skipLinkType = []
            graph_new = _graph_create()
            for link in graph["linkList"]:
                if link["to"]["category"] == "class-datatype":
                    continue
                if link["to"]["category"] == "class-datastructure":
                    continue

                if link["to"]["name"] == "CnsLink":
                    continue #not need to show super class relation for this case

                #logging.info(json4debug(link))
                graph_new["linkList"].append(link)
                graph_new["nodeMap"]["class"].add(_get_definition_name(link["from"]))
                graph_new["nodeMap"]["class"].add(_get_definition_name(link["to"]))

                if link["type"] in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                    pass
                elif link["type"] in ["property_domain_range"]:
                    graph_new["nodeMap"]["property"].add(_get_definition_name(link["relation"]))
                    pass
                elif link["type"] in ["template_link"]:
                    graph_new["nodeMap"]["link"].add(_get_definition_name(link["relation"]))
                else:
                    graph_new["nodeMap"]["property"].add(_get_definition_name(link["relation"]))

            graph_new["nodeMap"]["class"] = graph_new["nodeMap"]["class"].difference( graph_new["nodeMap"]["link"] )
            graph_new["nodeMap"]["class"] = graph_new["nodeMap"]["class"].difference( graph_new["nodeMap"]["property"] )
            return graph_new

        def _render_dot_format(graph, key, subgraph_name=None):
            # generate graph
            lines = []
            if subgraph_name == None:
                lines.append(u"digraph {} ".format(name))
            else:
                lines.append(u"subgraph cluster_{} ".format(subgraph_name))

            lines.append("{")
            line = "\t# dot -Tpng local/{}_full.dot -olocal/{}_{}.png".format(name, name, key)
            lines.append(line)
            logging.info(line)

            if not subgraph_name is None:
                line = "\tlabel={}".format(subgraph_name)
                lines.append(line)
                #lines.append('\trankdir = "TD"')
            else:
                lines.append('\trankdir = "LR"')
            #nodes
            lines.append('\n\tnode [shape=oval]')
            lines.extend(sorted(list(graph["nodeMap"]["class"])))
            lines.append("")

            lines.append('\n\tnode [shape=doubleoctagon]')
            lines.extend(sorted(list(graph["nodeMap"]["link"])))
            lines.append("")

            lines.append('\n\tnode [shape=octagon]')
            lines.extend(sorted(list(graph["nodeMap"]["property"])))
            lines.append("")

            #links
            for link in graph["linkList"]:
                if link["type"] in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                    line = u'\t{} -> {}\t [style=dotted]'.format(
                        _get_definition_name(link["from"]),
                        _get_definition_name(link["to"]) )
                    if line not in lines:
                        lines.append(line)
                else:
                    line = u'\t{} -> {}\t '.format(
                        _get_definition_name(link["from"]),
                        _get_definition_name(link["relation"]))
                    if line not in lines:
                        lines.append(line)

                    line = u'\t{} -> {}\t '.format(
                        _get_definition_name(link["relation"]),
                        _get_definition_name(link["to"]))
                    if line not in lines:
                        lines.append(line)
            lines.append(u"}")

            ret = u'\n'.join(lines)
            return ret

        def _graph_create():
            return {
                "linkList":[],
                "nodeMap":collections.defaultdict(set),
            }

        def _graph_update(schema, graph):
            # preprare data

            for definition in sorted(schema.definition.values(), key=lambda x:x["@id"]):
                # domain range relation
                _add_domain_range(definition, graph)

                _addSuperClassProperty(definition, graph)
                pass

            map_link_in_out = collections.defaultdict(dict)
            for template in schema.metadata["template"]:
                _add_template_domain_range(template, graph, map_link_in_out)

            for key in sorted(map_link_in_out):
                link = map_link_in_out[key]
                _add_graphviz_link(link, graph)
            return graph


        ret = {}

        key = "full"
        graph = _graph_create()
        _graph_update(self, graph)
        ret[key] = _render_dot_format(graph, key)

        key = "compact"
        graph_new = _filter_compact(graph)
        ret[key] = _render_dot_format(graph_new, key)

        key = "import"
        subgraphs = []
        lines = []
        line = "digraph import_%s {" % (self.metadata["name"])
        lines.append(line)
        lines.append('\trankdir = "LR"')

        for schema in self.loaded_schema_list:
            graph = _graph_create()
            if schema.metadata["name"] == "cns_top":
                continue
            _graph_update(schema, graph)
            graph_new = _filter_compact(graph,)
            subgraph = _render_dot_format(graph_new,key, schema.metadata["name"])
            lines.append(subgraph)
        line = "}"
        lines.append(line)
        ret[key] = u'\n'.join(lines)
        #logging.info(ret)
        return ret

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

    def import_jsonld(self, filename=None, preloadSchemaList={}):
        #reset data
        jsonld = file2json(filename)
        return self.import_jsonld_content(jsonld, preloadSchemaList)

    def import_jsonld_content(self, jsonld, preloadSchemaList={}):
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

        self.build(preloadSchemaList)

def task_importJsonld(args):
    logging.info( "called task_importJsonld" )
    filename = args["input_file"]
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(filename)

    #validate if we can reproduce the same jsonld based on input
    jsonld_input = file2json(filename)

    xdebug_file = os.path.join(args["debug_dir"],os.path.basename(args["input_file"]))
    filename_debug = xdebug_file+u".debug-2"
    jsonld_output = loaded_schema.export_jsonld(filename_debug)

    assert len(jsonld_input) == len(jsonld_output)
    x = json4debug(jsonld_input).split("\n")
    y = json4debug(jsonld_output).split("\n")
    for idx, line in enumerate(x):
        if x[idx] != y[idx]:
            logging.info(json4debug([idx, x[idx],y[idx]]) )
            break

def task_convert(args):
    logging.info( "called task_convert" )
    filename = "../schema/cns_top.jsonld"
    filename = file2abspath(filename, __file__)
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(filename)

    filename = args["input_file"]
    jsondata = file2json(filename)
    report = loaded_schema.init_report()
    for idx, item in enumerate(jsondata):
        types = [item["mainType"], "Thing"]
        primary_keys = [idx]
        cnsItem = loaded_schema.cnsConvert(item, types, primary_keys, report)
        logging.info(json4debug(cnsItem))
        loaded_schema.run_validate(cnsItem, report)
    logging.info(json4debug(report))

def task_validate(args):
    logging.info( "called task_validate" )
    schema_filename = args.get("input_schema")
    if not schema_filename:
        schema_filename = "schema/cns_top.jsonld"

    preloadSchemaList = preload_schema()
    loaded_schema = CnsSchema()
    loaded_schema.import_jsonld(schema_filename, preloadSchemaList)

    filename = args["input_file"]
    if args.get("option") == "jsons":
        report = loaded_schema.init_report()
        for idx, line in enumerate(file2iter(filename)):
            if idx % 10000 ==0:
                logging.info(idx)
                logging.info(json4debug(report))
            json_data = json.loads(line)
            loaded_schema.run_validateRecursive(json_data, report)
            stat_kg_report_per_item(json_data, None, report["stats"])
        logging.info(json4debug(report))

    else:
        jsondata = file2json(filename)
        report = loaded_schema.init_report()
        loaded_schema.run_validateRecursive(jsondata, report)
        logging.info(json4debug(report))

def preload_schema():
    logging.info("preload_schema")
    schemaNameList = ["cns_top","cns_place","cns_person","cns_creativework","cns_organization"]
    preloadSchemaList = {}
    for schemaName in schemaNameList:
        filename = u"../schema/{}.jsonld".format(schemaName)
        filename = file2abspath(filename)
        if not os.path.exists(filename):
            filename = u"../resources/cnschema/{}.jsonld".format(schemaName)
            filename = file2abspath(filename)

        loaded_schema = CnsSchema()
        loaded_schema.import_jsonld(filename, preloadSchemaList)
        preloadSchemaList[schemaName] = loaded_schema
        logging.info("loaded {}".format(schemaName))
    logging.info(len(preloadSchemaList))
    return preloadSchemaList

def task_graphviz(args):
    #logging.info( "called task_graphviz" )

    filename = args["input_file"]
    loaded_schema = CnsSchema()
    preloadSchemaList = preload_schema()
    loaded_schema.import_jsonld(filename, preloadSchemaList)

    #validate if we can reproduce the same jsonld based on input
    jsonld_input = file2json(filename)

    name = os.path.basename(args["input_file"]).split(u".")[0]
    name = re.sub(ur"-","_", name)
    ret = loaded_schema.run_graphviz(name)
    for key, lines in ret.items():
        xdebug_file = os.path.join(args["debug_dir"], name+"_"+key+u".dot")
        lines2file([lines], xdebug_file)

if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--input_schema': 'input schema',
        '--output_file': 'output file',
        '--debug_dir': 'debug directory',
        '--option': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    # task 1: import jsonld (and is loaded completely)
    python kgtool/cns_schema.py task_importJsonld --input_file=schema/cns_top.jsonld --debug_dir=local/
    python kgtool/cns_schema.py task_importJsonld --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
    python kgtool/cns_schema.py task_importJsonld --input_file=schema/cns_organization.jsonld --debug_dir=local/

    # task 2: convert
    python kgtool/cns_schema.py task_convert --input_file=tests/test_cns_schema_input1.json --debug_dir=local/

    python kgtool/cns_schema.py task_convert_excel --input_file=tests/test_cns_schema_input1.json --input_schema=schema/cns_top.jsonld --debug_dir=local/

    # task 3: validate
    python kgtool/cns_schema.py task_validate --input_file=schema/cns_top.jsonld --debug_dir=local/
    python kgtool/cns_schema.py task_validate --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
    python kgtool/cns_schema.py task_validate --input_file=tests/test_cns_schema_input1.json --debug_dir=local/

    python kgtool/cns_schema.py task_validate --input_file=tests/test_cns_schema_input1.json --debug_dir=local/


    # task 4: graphviz
    python kgtool/cns_schema.py task_graphviz --input_file=schema/cns_top.jsonld --debug_dir=local/
    python kgtool/cns_schema.py task_graphviz --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
    python kgtool/cns_schema.py task_graphviz --input_file=schema/cns_organization.jsonld --debug_dir=local/

"""
