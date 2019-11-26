#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Li Ding

import copy
import glob
from difflib import unified_diff
import urllib

from kgtool.core import *  # noqa
from kgtool.alg_graph import DirectedGraph
from kgtool.cns_common import CnsBugReport

# global constants
VERSION = 'v20180920'
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




def preload_schema(args=None):
    schema_dir = args.get("schema_dir")
    if not schema_dir:
        schema_dir = "cnschema"

    filename_list = glob.glob(u"{}/*.jsonld".format(schema_dir))

    for filename in filename_list:
        loaded_schema = CnsSchema()
        loaded_schema.jsonld2mem4file(filename)
        schema_identifier = loaded_schema.metadata["identifier"]
        #logging.info(json4debug(loaded_schema.metadata))
        loaded_schema.preloaded_schema_list[schema_identifier] = loaded_schema
        logging.info("loaded {}".format(schema_identifier))

    logging.info(len(loaded_schema.preloaded_schema_list))
    return loaded_schema.preloaded_schema_list


def _extract_alias_list(cns_item):
    prop_list = ["name", "refProperty", "alternateName", "propertyAlternateName"]
    ret = []
    for prop in prop_list:
        ret.extend(json_get_list(cns_item, prop))
    return sorted(list(set(ret)))


def gen_range_validation_config(range_text, schema):
    temp = {"text": range_text, "python_type_value_list": [], "cns_range_entity": [], "cns_range_datastructure": []}
    for r in parse_list_value(range_text):
        if range_text.lower() in ["text", "date", "datetime", "number", "url"]:
            temp["python_type_value_list"].extend([str])
        elif range_text.lower() in ["integer"]:
            temp["python_type_value_list"].append(int)
        elif range_text.lower() in ["float"]:
            temp["python_type_value_list"].append(float)
            temp["python_type_value_list"].append(int)
        elif "CnsDataStructure" in schema.index_inheritance["rdfs:subClassOf"].get(r, []):
            temp["cns_range_datastructure"].append(range_text)
        else:
            temp["cns_range_entity"].append(range_text)

    return temp


class CnsSchema:
    def __init__(self):
        self.report = CnsBugReport()

        # Schema metadata (template/changelog/metadata)
        self.metadata = collections.defaultdict(list)

        # Schema raw data: concept definition,  @id => entity
        self.definition = collections.defaultdict(dict)

        # schema dependency pairs e.g. {(cns_top_v2.1, cns_meta_v2.1), (cns_place_v2.1, cns_top_v2.1)}
        self._schema_dependency = set()

        # all schema module, includion self
        self.imported_schema = []

        self.schema_dir = "schema"
        self.schema_urlprefix = None
        self.preloaded_schema_list = {}


        # index: 属性名称映射表  property alias => property standard name
        self.index_property_alias = {}

        # index: 定义名称映射表  defintion alias => definition（property/class）
        self.index_definition_alias = {}

        # index: VALIDATION  class => template Object
        self.index_validate_template = collections.defaultdict(dict)

        # index: VALIDATION  property => expected types
        self.index_validate_domain = collections.defaultdict(list)

        # index: VALIDATION  property =>  range
        self.index_validate_range = collections.defaultdict(dict)

        # index: subclass/subproperty inheritance  class/property to all its super ones
        self.index_inheritance = collections.defaultdict(dict)


    def set_definition(self, item):
        assert "@id" in item
        self.definition[item["@id"]] = item

    def get_definition(self, xid):
        return self.definition.get(xid)

    def get_definition_by_alias(self, alias):
        return self.index_definition_alias.get(alias)

    def add_metadata(self, group, item):
        """
            only  template, changelog, import, keywords can be list,
            other must remain the same
        """
        if group in [ "template", "changelog"]:
            self.metadata[group].append(item)
        elif group in ["import"]:
            if type(item) == list:
                self.metadata[group].extend(item)
            else:
                self.metadata[group].append(item)
        else:
            self.metadata[group] = item


    def load_jsonld(self, schema_release_identifier ):
        if self.schema_urlprefix:
            schema_url = "{}/{}".format(self.schema_urlprefix, schema_release_identifier)
            response = urllib.urlopen(schema_url)
            text = response.read()
            return json.loads(text)
        elif self.schema_dir:
            for schema_dir in  [self.schema_dir, "schema","local/schema"]:
                filename = "{}/{}.jsonld".format(schema_dir, schema_release_identifier)
                logging.info(filename)
                if os.path.exists(filename):
                    return file2json(filename)
            assert False # cannot find file in any schema dir
        else:
            assert False # neither URL or local schema dir supplied

    def build(self):

        self._complete_imported_schema_list()

        self._build_index_definition_alias()
        self._build_index_inheritance()

        self._complete_template_definition_reference()

        self._build_index_template()

        self._build_index_property_alias()
        #self._build_index_range(self.imported_schema)
        #self._build_index_domain(self.imported_schema)

        # logging.info([x.metadata["name"] for x in self.imported_schema])
        # self._validate_schema()

        self._stat()

    def _import_one_schema(self, schema_identifier):
        schema = self.preloaded_schema_list.get(schema_identifier)
        if not schema:
            # load schema on demand
            jsonld = self.load_jsonld(schema_identifier)
            #filename = u"../schema/{}.jsonld".format(schema_identifier)
            #filename = file2abspath(filename)
            #logging.info("import schema " + filename)
            schema = CnsSchema()
            schema.preload_schema_list = self.preloaded_schema_list

            schema.jsonld2mem(jsonld)

        assert schema, schema_identifier
        logging.info("importing {}".format(schema_identifier))

        self.preloaded_schema_list[schema_identifier] = schema
        return schema

    def _complete_imported_schema_list(self):
        self_id = self.metadata["identifier"]
        # handle import
        for schema_identifier in self.metadata["import"]:
            schema = self._import_one_schema(schema_identifier)
            # update schema dependency from imported schema
            self._schema_dependency.update(schema._schema_dependency)
            # self depends on schema_identifier
            self._schema_dependency.add((self_id, schema_identifier))

        # compute full imported schemas
        if self._schema_dependency:
            dg = DirectedGraph(self._schema_dependency)
            st = dg.compute_subtree(include_self=False)
            assert self_id in st
            self.imported_schema = list(reversed([self.preloaded_schema_list[s] for s in st[self_id]]))

        self.imported_schema.append(self)

    # def _validate_schema(self):
    #     for template in self.metadata["template"]:
    #         cls = self.index_definition_alias.get(template["refClass"])
    #         # logging.info(json4debug(sorted(self.index_definition_alias.keys())))
    #         if cls is None:
    #             bug = {
    #                 "category": "error_template_refClass_undefined",
    #                 "description": "template definition refClass {} not defined in schema".format(cls),
    #                 "value" : template
    #             }
    #         assert cls, template  # missing class definition
    #         assert cls["name"] == template["refClass"]
    #         assert cls["@type"][0] == "rdfs:Class"
    #
    #         prop = self.index_definition_alias.get(template["refProperty"])
    #         assert prop, template  # refProperty not defined
    #         assert prop["name"] == template["refProperty"], template["refProperty"]
    #         assert prop["@type"][0] == "rdf:Property"

    def _stat(self):
        self.stat = collections.Counter()
        for cnsItem in self.definition.values():
            if "CnsProperty" in cnsItem["@type"]:
                self.stat["cntProperty"] += 1
            elif "CnsClass" in cnsItem["@type"]:
                self.stat["cntClass"] += 1

        self.stat["cntTemplate"] += len(self.metadata["template"])

        self.stat["cntTemplateGroup"] += len(set([x["refClass"] for x in self.metadata["template"]]))

        logging.info(self.metadata["identifier"])
        logging.info(self.stat)

    def get_all_property(self):
        ret = []
        for schema in self.imported_schema:
            for definition in schema.definition.values():
                if "CnsProperty" in definition["@type"]:
                    ret.append(definition["name"])
        return sorted(list(set(ret)))

    def get_super_class(self, xtype):
        return self.index_inheritance["rdfs:subClassOf"].get(xtype)

    def get_main_types(self, types):
        parents = set()
        for xtype in types:
            ret = self.index_inheritance["rdfs:subClassOf"].get(xtype)
            if ret:
                parents.update(ret[1:])
            elif xtype.startswith("rdf"):
                pass
            else:
                logging.warn(xtype)
        ret = set(types).difference(parents)
        return ret

    def get_best_template(self, types, p):
        for xtype in types:
            template = self.index_validate_template.get(xtype, {}).get(p)
            if template:
                return template

    def get_template_for_property_alias(self, types, alias):
        template_map = self.index_property_alias.get(alias)
        if not template_map:
            return None

        if not types:
            return template_map.values()[0]
        else:
            for template in template_map.values():
                if template["refClass"] in types:
                    return template

        return None

    def _build_index_inheritance(self):
        # list all direct class hierarchy pairs
        plist = ["rdfs:subClassOf", "rdfs:subPropertyOf"]
        direct_sub = collections.defaultdict(list)
        for schema in self.imported_schema:
            for cns_item in schema.definition.values():
                for p in plist:
                    if p in cns_item:
                        for v in cns_item[p]:
                            direct_sub[p].append([cns_item["name"], v])

        # logging.info(json4debug(direct_sub))

        # compute indirect class hierarchy relations
        self.index_inheritance = collections.defaultdict(dict)
        for p in direct_sub:
            dg = DirectedGraph(direct_sub[p])
            self.index_inheritance[p] = dg.compute_subtree()

        # complete with all definition
        for schema in self.imported_schema:
            for cns_item in schema.definition.values():
                if "CnsProperty" in cns_item["@type"]:
                    p = "rdfs:subPropertyOf"
                else:
                    p = "rdfs:subClassOf"
                n = cns_item["name"]
                if n not in self.index_inheritance[p]:
                    self.index_inheritance[p][n] = [n]

        # logging.info( json4debug(self.index_inheritance ))

    # def _build_index_range(self):
    #     # reset
    #     self.index_validate_range = {}
    #
    #     # init system property
    #     self.index_validate_range["@id"] = {"text": "UUID", "python_type_value_list": [basestring, unicode, str]}
    #     self.index_validate_range["@type"] = {"text": "Text", "python_type_value_list": [basestring, unicode, str]}
    #     #        self.index_validate_range ["@context"] = {"text": "SYS", "cns_range_list": []}
    #     self.index_validate_range["@graph"] = {"text": "SYS", "cns_range_list": ["CnsMetadata"]}
    #     self.index_validate_range["rdfs:domain"] = {"text": "SYS", "python_type_value_list": [basestring, unicode, str]}
    #     self.index_validate_range["rdfs:range"] = {"text": "SYS", "python_type_value_list": [basestring, unicode, str]}
    #     self.index_validate_range["rdfs:subClassOf"] = {"text": "SYS",
    #                                                     "python_type_value_list": [basestring, unicode, str]}
    #     self.index_validate_range["rdfs:subPropertyOf"] = {"text": "SYS",
    #                                                        "python_type_value_list": [basestring, unicode, str]}
    #
    #     # build
    #     for schema in self.imported_schema:
    #         for cns_item in schema.definition.values():
    #             if cns_item["name"] in ["@id", "@type"]:
    #                 assert False, json4debug(cns_item)
    #
    #             if "rdf:Property" in cns_item["@type"] and "rdfs:range" in cns_item:
    #                 # logging.info(json4debug(cns_item))
    #                 p = cns_item["name"]
    #                 r = cns_item["rdfs:range"]
    #                 # assert type(r) == list
    #                 if p not in self.index_validate_range:
    #                     temp = {"text": r}
    #                     if r in ["Text", "Date", "DateTime", "Number", "URL"]:
    #                         temp["python_type_value_list"] = [basestring, unicode, str]
    #                     elif r in ["Integer"]:
    #                         temp["python_type_value_list"] = [int]
    #                     elif r in ["Float"]:
    #                         temp["python_type_value_list"] = [float]
    #                     else:
    #                         temp["cns_range_list"] = [r]
    #
    #                     self.index_validate_range[p] = temp
    #
    # def _build_index_domain(self):
    #     # reset
    #     self.index_validate_domain = collections.defaultdict(list)
    #
    #     # init system property
    #     self.index_validate_domain["@id"] = ["Thing", "Link", "CnsMetadata"]
    #     self.index_validate_domain["@type"] = ["Thing", "Link", "CnsMetadata", "CnsDataStructure"]
    #     self.index_validate_domain["@context"] = ["CnsOntology"]
    #     self.index_validate_domain["@graph"] = ["CnsOntology"]
    #     self.index_validate_domain["rdfs:domain"] = ["rdf:Property"]
    #     self.index_validate_domain["rdfs:range"] = ["rdf:Property"]
    #     self.index_validate_domain["rdfs:subClassOf"] = ["rdfs:Class"]
    #     self.index_validate_domain["rdfs:subPropertyOf"] = ["rdf:Property"]
    #
    #     # build
    #     for schema in self.imported_schema:
    #         for cns_item in schema.definition.values():
    #             # should not define system properties
    #             if cns_item["name"] in ["@id", "@type"]:
    #                 assert False, json4debug(cns_item)
    #
    #             # regular properties only
    #             if "rdf:Property" in cns_item["@type"] and "rdfs:domain" in cns_item:
    #                 p = cns_item["name"]
    #                 d = cns_item["rdfs:domain"]
    #                 # assert type(r) == list
    #                 if isinstance(d, list):
    #                     self.index_validate_domain[p].extend(d)
    #                 else:
    #                     self.index_validate_domain[p].append(d)
    #
    #                 # special hack
    #                 if d in ["Top"]:
    #                     self.index_validate_domain[p].extend(["Thing", "CnsLink", "CnsMetadata", "CnsDataStructure"])
    #
    #     # dedup
    #     for p in self.index_validate_domain:
    #         self.index_validate_domain[p] = sorted(set(self.index_validate_domain[p]))

    def _complete_template_definition_reference(self):
        logging.info("enter")
        # reset
        self.index_validate_template = collections.defaultdict(dict)

        # build
        for schema in self.imported_schema:
            for template in schema.metadata["template"]:
                class_definition = self.get_definition_by_alias(template["refClass"])
                if not class_definition:
                    bug = {
                        "category" : "error_template_class_reference_undefined",
                        "description" : "template refClass={} refProperty={}, missing class definition".format(template["refClass"], template["refProperty"]),
                        "value": template
                    }
                    self.report.report_bug( bug)
                    #logging.info(len(self.index_definition_alias))
                    #logging.info(json4debug(bug))
                    #assert False
                    continue

                #if template.get("propertyRange"):
                if not template.get("propertySchema"):
                    continue

                #logging.info(template["name"])

                property_definition = self.get_definition_by_alias(template["refProperty"])
                if not property_definition:
                    bug = {
                        "category" : "error_template_property_reference_undefined",
                        "description" : "template refClass={} refProperty={}, missing property definition".format(template["refClass"], template["refProperty"]),
                        "value": template
                    }
                    self.report.report_bug( bug)
                    continue

                p = "propertyRange"
                if not template.get(p):
                    template[p] = property_definition["range"]
                p = "propertyNameZh"
                if not template.get(p):
                    template["propertyNameZh"] = property_definition["nameZh"]
                p = "propertyAlternateName"
                if not template.get(p):
                    template["propertyAlternateName"] = property_definition.get("alternateName",[])
            #   template["category"] = "property-template"



    def _build_index_template(self):
        logging.info("enter")
        # reset
        self.index_validate_template = collections.defaultdict(dict)

        # build
        for schema in self.imported_schema:
            for template in schema.metadata["template"]:
                # clean min/max cardinality

                p = "minCardinality"
                if p not in template or template[p] in ["",0,"0"]:
                    template[p] = 0
                elif template[p] in [0, 1, "0","1"]:
                    template[p] = int(template[p])
                elif isinstance(template[p], float):
                    template[p] = int(template[p])
                else:
                    bug = {
                        "category" : "warn_template_unexpected_value",
                        "description" : "template has unexpected value,  {}={}".format(p, template[p]),
                        "value": template
                    }
                    self.report.report_bug( bug)
                    assert template[p] in [0, 1], template


                p = "maxCardinality"
                if p not in template:
                    pass
                elif template[p] in [1, "1"]:
                    template[p] = int(template[p])
                elif isinstance(template[p], float):
                    template[p] = int(template[p])
                elif template[p] == "":
                    del template[p]
                else:
                    bug = {
                        "category" : "warn_template_unexpected_value_{}".format(p),
                        "description" : "template has unexpected value, {}={}".format(p, template[p]),
                        "value": template
                    }
                    self.report.report_bug( bug)
                    assert False, template

                # build index for validation
                template_validation = copy.deepcopy(template)
                p = "propertyRange"
                if template.get(p):
                    template_validation[p] = gen_range_validation_config(template.get(p), self)

                    d = template["refClass"]
                    rp = template["refProperty"]
                    self.index_validate_template[d][rp] = template_validation

    def _build_index_property_alias(self):
        self.index_property_alias = collections.defaultdict(dict)

        # build alias
        for schema in self.imported_schema:
            for template in schema.metadata["template"]:
                alias_list = []
                alias_list.extend( json_get_list(template, "propertyAlternateName"))
                alias = template.get("propertyNameZh")
                if alias:
                    alias_list.append( alias )
                alias = template.get("refProperty")
                if alias:
                    alias_list.append( alias )

                for alias in alias_list:
                    self.index_property_alias[alias][template["name"]] = template

        # validate
        for alias, v in self.index_property_alias.items():
            #            logging.info(alias)
            if len(v) > 1:
                bug = {
                    "category": "info_definition_duplicated_name",
                    "description": u"found alias=[{}] associated with more than one definitions [{}]".format(
                        alias, u", ".join(v.keys()))
                }
                #self.report.report_bug( bug)
                #assert len(v) == 1, (alias, list(v))
            #self.index_property_alias[alias] = list(v)[0]

    def _build_index_definition_alias(self):
        self.index_definition_alias = {}

        map_name_item = collections.defaultdict(list)

        # collect alias from definition
        for schema in self.imported_schema:
            for cns_item in schema.definition.values():
                # cns_item["statedIn"] = schema.metadata["name"]
                cns_item["statedIn"] = schema.metadata["name"]

                if "cns_schemaorg" == schema.metadata["name"]:
                    if cns_item["@id"] in self.imported_schema[0].definition:
                        # if definition is defined in cns_top, then
                        # skip schemaorg's defintion
                        continue

                for alias in _extract_alias_list(cns_item):
                    map_name_item[alias].append(cns_item)

        # validate
        for alias, v in map_name_item.items():
            if len(v) > 1:
                #logging.info(json4debug(v))
                bug = {
                    "category": "error_definition_duplicated_name",
                    "description": u"found alias=[{}] associated with more than one definitions [{}]".format(
                        alias, u", ".join([x["name"] for x in v])),
                    "value": v

                }
                self.report.report_bug( bug)
                # assert len(v) == 1, alias
            self.index_definition_alias[alias] = v[0]

        # add system
        self.index_definition_alias["rdfs:domain"] = {"name": "domain"}
        self.index_definition_alias["rdfs:range"] = {"name": "range"}
        self.index_definition_alias["rdfs:subClassOf"] = {"name": "subClassOf"}
        self.index_definition_alias["rdfs:subPropertyOf"] = {"name": "subPropertyOf"}
    #    self.index_definition_alias["rdf:Property"] = {"name": "Property"}
    #    self.index_definition_alias["rdfs:Class"] = {"name": "Class"}
        # self.index_definition_alias["@graph"] = {"name":"subPropertyOf"}
        # self.index_definition_alias["@context"] = {"name":"subPropertyOf"}

        #logging.info(len(schema.definition))
        # assert len(self.index_definition_alias)>4


    def jsonld2mem4file(self, filename=None):
        # reset data
        jsonld = file2json(filename)
        return self.jsonld2mem(jsonld)

    def jsonld2mem(self, jsonld):
        # load
        assert jsonld["@context"]["@vocab"] == "http://cnschema.org/"

        for p in jsonld:
            if p.startswith("@"):
                pass
            elif p in ["template", "changelog"]:
                for v in jsonld[p]:
                    self.add_metadata(p, v)
            else:
                #logging.info((p,jsonld[p]))
                self.add_metadata(p, jsonld[p])

        for definition in jsonld["@graph"]:
            self.set_definition(definition)

        self.build()

    def mem2jsonld(self, filename=None):

        if not self.metadata["identifier"]:
            bug = {
                "category" : "error_ontology_release_missing_identifier",
                "description" : "ontology release, sheet=metadata missing identifier",
            }
            self.report.report_bug( bug)
            return {}

        if not self.metadata["name"]:
            bug = {
                "category" : "error_ontology_release_missing_name",
                "description" : "ontology release, sheet=metadata missing name",
            }
            self.report.report_bug( bug)
            return {}

        xid_release = "http://meta.cnschema.org/ontologyrelease/{}".format(self.metadata["identifier"])
        xid_schema = "http://meta.cnschema.org/ontology/{}".format(self.metadata["name"])


        # assign metadata values
        jsonld = {"@context": {
                        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                        "@vocab": "http://cnschema.org/"
                    },
                    "@id": xid_release,
                    "@type": ["CnsOntologyRelease", "CnsMeta"],
                    "about": {
                        "@id": xid_schema,
                        "@type": ["CnsOntology", "CnsMeta"],
                        "name": self.metadata["name"],
                    },
                    "@graph": list(self.definition.values()) }

        for p in self.metadata:
            if p in ["changelog", "template"]:
                jsonld[p] = self.metadata[p]
            else:
                jsonld[p] = self.metadata[p]

        # sort, achieve cannonical representation (sorted)
        for p, v in jsonld.items():
            if p in ["@id", "@type", "import"]:
                continue

            if type(v) == list and p in ["template", "changelog", "@graph"]:
                #logging.info(json4debug(p))
                #logging.info(json4debug(v))
                jsonld[p] = sorted(v, key=lambda x: [x.get("@id", ""), x.get("name", "")])

        # save to file
        if filename:
            json2file(jsonld, filename)

        return jsonld

    def export_debug(self, filename=None):
        output = {
            u"index_property_alias_属性名称映射表": self.index_property_alias,
            u"index_definition_alias_定义名称映射表": self.index_definition_alias,
            u"index_validate_template": self.index_validate_template,
            u"index_validate_domain": self.index_validate_domain,
            # u"index_validate_range": self.index_validate_range,
            u"index_inheritance": self.index_inheritance,
        }

        # save to file
        if filename:
            json2file(output, filename)

        return output

def template2definition4property(cns_item_template):
    name = cns_item_template["refProperty"]
    xid = "http://cnschema.org/{}".format(name)

    cns_item_definition = {
        "@id": xid,
        "@type": ["CnsProperty", "CnsDefinition", "CnsMeta"],
        "name": name,
        "category": "property-template",
        "nameZh": cns_item_template["propertyNameZh"],
        "alternateName": parse_list_value(cns_item_template.get("propertyAlternateName","")),
        "rdfs:domain": parse_list_value(cns_item_template["refClass"]),
        "range": cns_item_template["propertyRange"],
    }
    return cns_item_definition


def task_import_schema(args):
    logging.info("enter")
    filename = args["input_file"]
    loaded_schema = CnsSchema()
    loaded_schema.jsonld2mem(filename)
    logging.info(filename)

    # validate if we can reproduce the same jsonld based on input
    jsonld_input = file2json(filename)

    xdebug_file = os.path.join(args["debug_dir"], os.path.basename(args["input_file"]))
    filename_debug = xdebug_file + u".debug-jsonld.json"
    jsonld_output = loaded_schema.mem2jsonld(filename_debug)

    assert len(jsonld_input) == len(jsonld_output)
    x = json4debug(jsonld_input).splitlines(1)
    y = json4debug(jsonld_output).splitlines(1)
    diff = unified_diff(x, y)
    logging.info(''.join(diff))
    for idx, line in enumerate(x):
        if x[idx] != y[idx]:
            logging.info(json4debug([idx, x[idx], y[idx]]))
            break

    filename_debug = xdebug_file + u".debug-memory.json"
    jsonld_output = loaded_schema.export_debug(filename_debug)




if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s',
                        level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--input_file': 'input file',
        '--schema_dir': 'input schema',
        '--debug_dir': 'debug directory',
    }
    main_subtask(__name__, optional_params=optional_params)

"""
    # task 1: import jsonld (and is loaded completely)
    python kgtool/cns_model.py task_import_schema --input_file=schema/cns_top.jsonld --debug_dir=local/debug --schema_dir=schema
    python kgtool/cns_model.py task_import_schema --input_file=schema/cns_schemaorg.jsonld --debug_dir=local/debug --schema_dir=schema
    python kgtool/cns_model.py task_import_schema --input_file=schema/cns_organization.jsonld --debug_dir=local/debug --schema_dir=schema

    python kgtool/cns_model.py task_import_schema --input_file=local/cns_fund_public.jsonld --debug_dir=local/debug --schema_dir=schema

"""
