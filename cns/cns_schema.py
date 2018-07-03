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

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('..'))

from kgtool.core import *  # noqa

# global constants
VERSION = 'v20180519'
CONTEXTS = [os.path.basename(__file__), VERSION]


"""
It stores cnSchema data:
 * definition: defintion of a class, property, or a constant
 * metadata: list of template restriction， changelog

It offers the following functions:
* cns loader: load a collection of cnSchema,
   * load class/property addDefinition
   * load template restriction metadata
   * load version metadata
   * validate unique name/alias of class/property,
* cnsConvert: convert non-cnSchema JSON into cnsItem using cnsSchema properties
* cnsValidate: validate integrity constraints imposed by template and property definition
   * class-property binding
   * property domain
   * property range
* cnsGraphviz: generate a graphviz dot format of a schema
"""

def _report(report, bug):
    msg = json.dumps(bug, ensure_ascii=False, sort_keys=True)
    report["bugs"].append(bug)
    return msg


class CnsSchema:
    def __init__(self):
        # Schema raw data: metadata information, key => value
        # version
        # template
        self.metadata = collections.defaultdict(list)

        # Schema raw data: concept definition,  @id => entity
        self.definition = collections.defaultdict(dict)

        # schema raw data: 引用相关Schema
        self.importSchema = []


        #index: 属性名称映射表  property alias => property standard name
        self.indexPropertyAlias = {}

        #index: 定义名称映射表  defintion alias => definition（property/class）
        self.indexDefinitionAlias = {}

        #index: VALIDATION  class => template Object
        self.indexValidateTemplate = collections.defaultdict( dict )

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
            * template restriction  (class-property binding)

            * range of property
        """
        report["stats"]["items_validated"] += 1

        if not self._validateSystem(cnsItem, report):
            return report

        self._validateTemplate(cnsItem, report)

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
        # template validation
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

    def _validateTemplate(self, cnsItem, report):
        # template validation
        validated_property = set()
        for xtype in cnsItem["@type"]:
            for template in self.indexValidateTemplate[xtype]:
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
                        "item": cnsItem
                    }
                    logging.warn(_report(report, bug))


                if "maxCardinality" in template:
                    if cardAcual > template["maxCardinality"]:
                        bug = {
                            "category": "warn_validate_template",
                            "text": "maxCardinality",
                            "property": p,
                            "expected": template["maxCardinality"],
                            "actual": cardAcual,
                            "item": cnsItem
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
            "@id" : item.get("@id", any2sha256( primaryKeys ))
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
        def _buildImportedSchema(schema):
            #handle import
            name = schema.metadata["name"]
            importedCnsSchema = []
            importedSchemaName = []
            if name != "cns_top":
                importedSchemaName.append( "cns_top" )

            #logging.info(json4debug(schema.metadata))
            importedSchemaName.extend( json_get_list(schema.metadata, "import") )
            #logging.info(json4debug(schema.metadata["import"]))
            #assert False

            #logging.info(json4debug(importedSchemaName))
            for schemaName in importedSchemaName:
                filename = u"../schema/{}.jsonld".format(schemaName)
                filename = file2abspath(filename)
                cnsSchema = CnsSchema()
                cnsSchema.importJsonLd(filename)
                importedCnsSchema.append(cnsSchema)
                logging.info("importing {}".format(schemaName))
            return importedCnsSchema

        schemaList = []
        #schemaList.extend( self.importSchema )
        schemaList.extend(_buildImportedSchema(self))
        schemaList.append(self)
        #logging.info(schemaList[0].metadata["name"])
        #assert False

        #if self.metadata['name'] == "cns_fund_public":
        #    logging.info(self.metadata['name'] )
        #    logging.info([x.metadata["name"] for x in schemaList])
        #    assert False

        self._buildindexPropertyAlias(schemaList)
        self._buildindexDefinitionAlias(schemaList)
        self._buildIndexRange(schemaList)
        self._buildIndexTemplate(schemaList)
        self._buildIndexDomain(schemaList)

        logging.info([x.metadata["name"] for x in schemaList])
        self._validateSchema()

        return self._stat()

    def _validateSchema(self):
        for template in self.metadata["template"]:
            cls = self.indexDefinitionAlias.get( template["refClass"] )
            #logging.info(json4debug(sorted(self.indexDefinitionAlias.keys())))
            assert cls, template
            assert cls["name"] == template["refClass"]
            assert cls["@type"][0] == "rdfs:Class"

            prop = self.indexDefinitionAlias.get( template["refProperty"] )
            assert prop, template
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
        logging.info(json4debug( ret ))
        return ret

    def _buildIndexRange(self, schemaList):
        #reset
        self.indexValidateRange = {}

        #init system property
        self.indexValidateRange["@id"] = {"text": "UUID", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange["@type"] = {"text": "Text", "pythonTypeValue":[basestring,unicode,str]}
#        self.indexValidateRange ["@context"] = {"text": "SYS", "cnsRange": []}
        self.indexValidateRange ["@graph"] = {"text": "SYS", "cnsRange": ["CnsMetadata"]}
        self.indexValidateRange ["rdfs:domain"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange ["rdfs:range"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange["rdfs:subClassOf"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}
        self.indexValidateRange["rdfs:subPropertyOf"] = {"text": "SYS", "pythonTypeValue":[basestring,unicode,str]}

        #build
        for schema in schemaList:
            for cnsItem in schema.definition.values():
                if cnsItem["name"] in ["@id", "@type"]:
                    assert False, json4debug(cnsItem)

                if "rdf:Property" in cnsItem["@type"] and "rdfs:range" in cnsItem:
                    #logging.info(json4debug(cnsItem))
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
        self.indexValidateDomain ["@id"] = ["Thing","Link", "CnsMetadata"]
        self.indexValidateDomain ["@type"] = ["Thing","Link", "CnsMetadata","CnsDataStructure"]
        self.indexValidateDomain ["@context"] = ["CnsOntology"]
        self.indexValidateDomain ["@graph"] = ["CnsOntology"]
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
                if "rdf:Property" in cnsItem["@type"] and "rdfs:domain" in cnsItem:
                    p = cnsItem["name"]
                    d = cnsItem["rdfs:domain"]
                    #assert type(r) == list
                    self.indexValidateDomain[p].append(d)

                    # special hack
                    if d in ["Top"]:
                        self.indexValidateDomain[p].extend(["Thing",CnsLink, "CnsMetadata", "CnsDataStructure"])


        # dedup
        for p in self.indexValidateDomain:
            self.indexValidateDomain[p] = sorted(set(self.indexValidateDomain[p]))

    def _buildIndexTemplate(self, schemaList):
        #reset
        self.indexValidateTemplate = collections.defaultdict(list)

        #build
        for schema in schemaList:
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

                self.indexValidateTemplate[d].append( template )

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
#            logging.info(alias)
            assert len(v) == 1, (alias, list(v))
            self.indexPropertyAlias[alias] = list(v)[0]

    def _buildindexDefinitionAlias(self, schemaList):
        self.indexDefinitionAlias = {}

        mapNameItem = collections.defaultdict(list)

        #collect alias from definition
        for schema in schemaList:
            for cnsItem in schema.definition.values():
                if "cns_schemaorg" == schema.metadata["name"]:
                    if cnsItem["@id"] in schemaList[0].definition:
                        # if definition is defined in cns_top, then
                        # skip schemaorg's defintion
                        continue

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

        #if self.metadata['name'] == "cns_fund_public":
        #    logging.info([x.metadata["name"] for x in schemaList])
        #    assert "Company" in self.indexDefinitionAlias

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


    def addMetadata(self, group, item):
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
            u"indexPropertyAlias_属性别名": self.indexPropertyAlias
        }

        #save to file
        if filename:
            json2file(output,filename)

        return output


    def cnsGraphviz(self, name):
        def _getName(definition):
            return u"{}（{}）".format(definition["name"], definition["nameZh"])

        def _addNode(definition, nodeMap):
            if definition is None:
                logging.warn("empty definition")
                return

            #logging.info(definition)
            if "rdf:Property" in definition["@type"]:
                p = "property"
            elif "CnsLink" in definition.get("rdfs:subClassOf",[]):
                p = "link"
            else:
                p = "class"
            nodeMap[p].add(_getName(definition))

        def _addLink(link, linkList, nodeMap):
            #logging.info(json4debug(link))
            linkList.append(link)
            _addNode(link["from"], nodeMap)
            _addNode(link["to"], nodeMap)
            if link["type"].endswith("domain_range") :
                _addNode(link["relation"], nodeMap)
            elif link["type"] == "template_link":
                _addNode(link["relation"], nodeMap)
            elif link["type"] in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                pass
            else:
                logging.info(json4debug(link))
                assert False

        def _addDomainRange(definition, linkList):
            #domain range relation
            if "rdf:Property" in definition["@type"]:
                if definition.get("rdfs:range") and definition.get("rdfs:domain"):
                    rangeClass = self.indexDefinitionAlias.get( definition["rdfs:range"] )
                    domainClass = self.indexDefinitionAlias.get( definition["rdfs:domain"] )
                    if domainClass and rangeClass:
                        link = {
                            "from": domainClass,
                            "to": rangeClass,
                            "relation": definition,
                            "type": "property_domain_range"
                        }
                        _addLink(link, linkList, nodeMap)

        def _addSuperClassProperty(definition, linkList):
            #super class/property relation
            for p in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                superList = definition.get(p,[])
                for super in superList:
                    superDefinition = self.indexDefinitionAlias.get(super)
                    if superDefinition:
                        link = {
                            "from": definition,
                            "to": superDefinition,
                            "type": p,
                        }
                        _addLink(link, linkList, nodeMap)

        def _addTemplateDomainRange(template, linkList, linkInOutMap):
            #logging.info(json4debug(template))
            #assert False


            if not template.get("refClass"):
                return
            if not template.get("refProperty"):
                return

            domainClass = self.indexDefinitionAlias.get( template["refClass"])
            if not domainClass:
                return

            propertyDefinition = self.indexDefinitionAlias.get(template["refProperty"])
            if not propertyDefinition:
                return


            if template.get("propertyRange"):
                rangeClass = self.indexDefinitionAlias.get( template["propertyRange"] )
            else:
                rangeClass = self.indexDefinitionAlias.get( propertyDefinition["rdfs:range"] )

            # special processing on  [in, out], system property for property graph
            assert rangeClass, template

            linkName = domainClass["name"]
            if template["refProperty"] in ["in"]:
                linkInOutMap[linkName]["from"] = rangeClass
                linkInOutMap[linkName]["relation"] = domainClass
                linkInOutMap[linkName]["type"] = "template_link"
            elif template["refProperty"] in ["out"]:
                linkInOutMap[linkName]["to"] = rangeClass
            else:
                link = {
                    "from": domainClass,
                    "to": rangeClass,
                    "relation": propertyDefinition,
                    "type": "template_domain_range"
                }
                _addLink(link, linkList, nodeMap)

        def _filterCompact(nodeMap, linkList):
            skipLinkType = []
            nodeMapNew = collections.defaultdict(set)
            linkListNew = []
            for link in linkList:
                if link["to"]["category"] == "class-datatype":
                    continue
                if link["to"]["category"] == "class-datastructure":
                    continue
                #logging.info(json4debug(link))
                linkListNew.append(link)
                nodeMapNew["class"].add(_getName(link["from"]))
                nodeMapNew["class"].add(_getName(link["to"]))

                if link["type"] in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                    pass
                elif link["type"] in ["property_domain_range"]:
                    pass
                elif link["type"] in ["template_link"]:
                    nodeMapNew["link"].add(_getName(link["relation"]))
                else:
                    nodeMapNew["property"].add(_getName(link["relation"]))

            nodeMapNew["class"] = nodeMapNew["class"].difference( nodeMapNew["link"] )
            return nodeMapNew, linkListNew

        def _renderDotFormat(nodeMap, linkList):
            # generate graph
            lines = []
            lines.append(u"digraph {} ".format(name))
            lines.append("{")
            line = "\t# dot -Tpng local/{}_full.dot -olocal/{}_full.png".format(name, name)
            lines.append(line)
            line = "\t# dot -Tpng local/{}_compact.dot -olocal/{}.png".format(name, name)
            lines.append(line)
            logging.info(line)
            lines.append('\trankdir = "LR"')
            #nodes
            lines.append('\n\tnode [shape=oval]')
            lines.extend(sorted(list(nodeMap["class"])))
            lines.append("")

            lines.append('\n\tnode [shape=doubleoctagon]')
            lines.extend(sorted(list(nodeMap["link"])))
            lines.append("")

            lines.append('\n\tnode [shape=octagon]')
            lines.extend(sorted(list(nodeMap["property"])))
            lines.append("")

            #links
            for link in linkList:
                if link["type"] in ["rdfs:subClassOf", "rdfs:subPropertyOf"]:
                    line = u'\t{} -> {}\t [style=dotted]'.format(
                        _getName(link["from"]),
                        _getName(link["to"]) )
                    if line not in lines:
                        lines.append(line)
                else:
                    line = u'\t{} -> {}\t '.format(
                        _getName(link["from"]),
                        _getName(link["relation"]))
                    if line not in lines:
                        lines.append(line)

                    line = u'\t{} -> {}\t '.format(
                        _getName(link["relation"]),
                        _getName(link["to"]))
                    if line not in lines:
                        lines.append(line)
            lines.append(u"}")

            ret = u'\n'.join(lines)
            return ret

        # preprare data
        linkList = []
        nodeMap = collections.defaultdict(set)

        for definition in sorted(self.definition.values(),key=lambda x:x["@id"]):
            # domain range relation
            _addDomainRange(definition, linkList)

            _addSuperClassProperty(definition, linkList)
            pass

        linkInOutMap = collections.defaultdict(dict)
        for template in self.metadata["template"]:
            _addTemplateDomainRange(template, linkList, linkInOutMap)

        for key in sorted(linkInOutMap):
            link = linkInOutMap[key]
            _addLink(link, linkList, nodeMap)

        ret = {
            "full": _renderDotFormat(nodeMap, linkList),
        }
        nodeMapNew, linkListNew = _filterCompact(nodeMap, linkList)
        ret["compact"] = _renderDotFormat(nodeMapNew, linkListNew)
        #logging.info(ret)
        return ret

    def exportJsonLd(self, filename=None):
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

    def importJsonLd(self, filename=None):
        #reset data

        #load
        jsonld = file2json(filename)
        assert jsonld["@context"]["@vocab"] == "http://cnschema.org/"

        for p in jsonld:
            if p.startswith("@"):
                pass
            elif p in ["template", "changelog"]:
                for v in jsonld[p]:
                    self.addMetadata(p, v)
            else:
                self.addMetadata(p, jsonld[p])



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

def task_convert(args):
    logging.info( "called task_graphviz" )
    filename = "../schema/cns_top.jsonld"
    filename = file2abspath(filename, __file__)
    cnsSchema = CnsSchema()
    cnsSchema.importJsonLd(filename)

    filename = args["input_file"]
    jsondata = file2json(filename)
    report = cnsSchema.initReport()
    for idx, item in enumerate(jsondata):
        types = [item["mainType"], "Thing"]
        primaryKeys = [idx]
        cnsItem = cnsSchema.cnsConvert(item, types, primaryKeys, report)
        logging.info(json4debug(cnsItem))
        cnsSchema.cnsValidate(cnsItem, report)
    logging.info(json4debug(report))


def task_validate(args):
    logging.info( "called task_graphviz" )
    filename = "../schema/cns_top.jsonld"
    filename = file2abspath(filename, __file__)
    cnsSchema = CnsSchema()
    cnsSchema.importJsonLd(filename)

    filename = args["input_file"]
    jsondata = file2json(filename)
    report = cnsSchema.initReport()
    cnsSchema.cnsValidateRecursive(jsondata, report)
    logging.info(json4debug(report))

def task_graphviz(args):
    logging.info( "called task_graphviz" )
    filename = args["input_file"]
    cnsSchema = CnsSchema()
    cnsSchema.importJsonLd(filename)

    #validate if we can reproduce the same jsonld based on input
    jsonld_input = file2json(filename)

    name = os.path.basename(args["input_file"]).split(u".")[0]
    name = re.sub(ur"-","_", name)
    ret = cnsSchema.cnsGraphviz(name)
    for key, lines in ret.items():
        xdebug_file = os.path.join(args["debug_dir"], name+"_"+key+u".dot")
        lines2file([lines], xdebug_file)

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
    python cns/cns_schema.py task_importJsonld --input_file=schema/cns_top.jsonld --debug_dir=local/
    python cns/cns_schema.py task_importJsonld --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
    python cns/cns_schema.py task_importJsonld --input_file=schema/cns_organization.jsonld --debug_dir=local/

    # task 2: convert
    python cns/cns_schema.py task_convert --input_file=tests/test_cns_schema_input1.json --debug_dir=local/

    # task 3: validate
    python cns/cns_schema.py task_validate --input_file=schema/cns_top.jsonld --debug_dir=local/
    python cns/cns_schema.py task_validate --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
    python cns/cns_schema.py task_validate --input_file=tests/test_cns_schema_input1.json --debug_dir=local/

    # task 4: graphviz
    python cns/cns_schema.py task_graphviz --input_file=schema/cns_top.jsonld --debug_dir=local/
    python cns/cns_schema.py task_graphviz --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/
    python cns/cns_schema.py task_graphviz --input_file=schema/cns_organization.jsonld --debug_dir=local/

"""
