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

# global constants
VERSION = 'v20180305'
CONTEXTS = [os.path.basename(__file__), VERSION]

###############
#  command line utitlity
def main_subtask(module_name, method_prefixs=["task_"], optional_params={}):
    """
    http://stackoverflow.com/questions/3217673/why-use-argparse-rather-than-optparse
    As of 2.7, optparse is deprecated, and will hopefully go away in the future
    """
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('method_name', help='')
    for optional_param_key, optional_param_help in optional_params.items():
        parser.add_argument(optional_param_key,
                            required=False,
                            help=optional_param_help)
        # parser.add_argument('--reset_cache', required=False, help='')
    args = parser.parse_args()

    for prefix in method_prefixs:
        if args.method_name.startswith(prefix):
            if prefix == "test_":
                # Remove all handlers associated with the root logger object.
                for handler in logging.root.handlers[:]:
                    logging.root.removeHandler(handler)

                # Reconfigure logging again, this time with a file.
                logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.DEBUG)  # noqa

            # http://stackoverflow.com/questions/17734618/dynamic-method-call-in-python-2-7-using-strings-of-method-names
            the_method = getattr(sys.modules[module_name], args.method_name)
            if the_method:
                the_method(args=vars(args))

                logging.info("done")
                return
            else:
                break

    logging.info("unsupported")


###############
#  file utilities


####################################
# file path


def file2abspath(filename, this_file=__file__):
    """
        generate absolute path for the given file and base dir
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(this_file)), filename))


####################################
# read from file

def file2json(filename, encoding='utf-8'):
    """
        save a line
    """
    with codecs.open(filename, "r", encoding=encoding) as f:
        return json.load(f)


def file2iter(filename, encoding='utf-8', comment_prefix="#",
              skip_empty_line=True):
    """
        json stream parsing or line parsing
    """
    ret = list()
    visited = set()
    with codecs.open(filename, encoding=encoding) as f:
        for line in f:
            line = line.strip()
            # skip empty line
            if skip_empty_line and len(line) == 0:
                continue

            # skip comment line
            if comment_prefix and line.startswith(comment_prefix):
                continue

            yield line


####################################
# write to file

def json2file(data, filename, encoding='utf-8'):
    """
        write json in canonical json format
    """
    with codecs.open(filename, "w", encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=False, indent=4, sort_keys=True)


def lines2file(lines, filename, encoding='utf-8'):
    """
        write json stream, write lines too
    """
    with codecs.open(filename, "w", encoding=encoding) as f:
        for line in lines:
            f.write(line)
            f.write("\n")


def items2file(items, filename, encoding='utf-8', modifier='w'):
    """
        json array to file, canonical json format
    """
    with codecs.open(filename, modifier, encoding=encoding) as f:
        for item in items:
            f.write(u"{}\n".format(json.dumps(
                item, ensure_ascii=False, sort_keys=True)))


####################################
# json data access

def json_get(json_object, property_path, default=None):
    """
        get value of property_path from a json object, e.g. person.father.name
        * invalid path return None
        * valid path (the -1 on path is an object), use default
    """
    temp = json_object
    for field in property_path[:-1]:
        if not isinstance(temp, dict):
            return None
        temp = temp.get(field, {})
    if not isinstance(temp, dict):
        return None
    return temp.get(property_path[-1], default)


def json_get_list(json_object, p):
    v = json_object.get(p, [])
    if isinstance(v, list):
        return v
    else:
        return [v]


def json_get_first_item(json_object, p, defaultValue=''):
    # return empty string if the item does not exist
    v = json_object.get(p, [])
    if isinstance(v, list):
        if len(v) > 0:
            return v[0]
        else:
            return defaultValue
    else:
        return v


def json_dict_copy(json_object, property_list, defaultValue=None):
    """
        property_list = [
            { "name":"name", "alternateName": ["name","title"]},
            { "name":"birthDate", "alternateName": ["dob","dateOfBirth"] },
            { "name":"description" }
        ]
    """
    ret = {}
    for prop in property_list:
        p_name = prop["name"]
        for alias in prop.get("alternateName", []):
            if json_object.get(alias) is not None:
                ret[p_name] = json_object.get(alias)
                break
        if not p_name in ret:
            if p_name in json_object:
                ret[p_name] = json_object[p_name]
            elif defaultValue is not None:
                ret[p_name] = defaultValue

    return ret

def json_append(obj, p, v):
    vlist = obj.get(p, [])
    if not isinstance(vlist, list):
        return

    if vlist:
        vlist.append(v)
    else:
        obj[p] = [v]

def json4debug(json_data, sort_keys=True):
    return json.dumps(json_data, ensure_ascii=False, indent=4, sort_keys=sort_keys)


####################################
# data conversion


def any2utf8(data):
    """
        rewrite json object values (unicode) into utf-8 encoded string
    """
    if isinstance(data, dict):
        ret = {}
        for k, v in data.items():
            k = any2utf8(k)
            ret[k] = any2utf8(v)
        return ret
    elif isinstance(data, list):
        return [any2utf8(x) for x in data]
    elif isinstance(data, unicode):
        return data.encode("utf-8")
    elif type(data) in [str, basestring]:
        return data
    elif type(data) in [int, float]:
        return data
    else:
        logging.error("unexpected {} {}".format(type(data), data))
        return data


def any2unicode(data):
    """
        rewrite json object values (assum utf-8) into unicode
    """
    if isinstance(data, dict):
        ret = {}
        for k, v in data.items():
            k = any2unicode(k)
            ret[k] = any2unicode(v)
        return ret
    elif isinstance(data, list):
        return [any2unicode(x) for x in data]
    elif isinstance(data, unicode):
        return data
    elif type(data) in [str, basestring]:
        logging.info("convert[{}]".format(data))
        return data.decode("utf-8")
    elif type(data) in [int, float]:
        return data
    else:
        logging.error("unexpected {} {}".format(type(data), data))
        return data


def any2sha1(text):
    """
        convert a string into sha1hash. For json object/array, first convert
        it into canonical json string.
    """
    # canonicalize json object or json array
    if type(text) in [dict, list]:
        text = json.dumps(text, sort_keys=True)

    # assert question as utf8
    if isinstance(text, unicode):
        text = text.encode('utf-8')

    return hashlib.sha1(text).hexdigest()


def any2sha256(text):
    """
        convert a string into sha256hash. For json object/array, first convert
        it into canonical json string.
    """
    # canonicalize json object or json array
    try:
        assert text
        #optimize list of text to speedup
        if type(text) in [list]:
            if len(text) == 1:
                text = text[0]
            else:
                text = u"___".join(text)
    except:
        pass

    if type(text) in [dict, list]:
        text = json.dumps(text, sort_keys=True)

    # assert question as utf8
    if isinstance(text, unicode):
        text = text.encode('utf-8')

    return hashlib.sha256(text).hexdigest()


####################################
# string parser

def parseListValue(value, regex=ur"[，,、；;／/]"):
    """
        parse unicode string into a list
        if the input is not unicode or list, raise exception
    """
    vtype = type(value)

    if vtype in [unicode]:
        ret = re.split(regex, value)
    elif vtype in [list]:
        ret = value
    else:
        assert False

    return [ x.strip() for x in ret if x != u'' ]


####################################
# object processor

def item2sample(item, counter=None):
    PCNT = "_cnt_dict"

    if type(item) in [list]:
        if len(item) > 0:
            return [item2sample(item[0], counter)]
        else:
            return []
    elif type(item) in [dict]:
        if counter is not None:
            counter[PCNT] += 1 #ince

        ret = {}
        for p,v in item.items():
            ret[p] = item2sample(v, counter)
        return ret
    else:
        return item



def normalize_value(v, option="list2sample"):
    """
        if value is empty, return None
        if value is not empty, should be converted to string, list, dict

        option=list2sample get the first item of a list as sample
        otherwise will return the full list

    """
    if v is None:
        return None
    xtype = type( v )
    if xtype in [ float, int ]:
        return "%1.0d" % v
    elif xtype in [dict, list]:
        if len(v) == 0:
            return None
        else:
            return v
    elif xtype in [unicode, basestring]:
        v = v.strip()
        if len(v) == 0:
            return None
        elif v in ["null","none"]:
            return None
        elif re.search(ur"^[\-\.\s]*$",v):
            return None
    return v


def item2flatstr(key, item, ret, option="list2sample"):
    item = normalize_value(item, option= option)
    if item is None:
        return

    xtype = type(item)
    if xtype in [dict]:
        for k, v in item.items():
            if key:
                keynew = u"{}.{}".format(key, k)
            else:
                keynew = k
            item2flatstr(keynew, v, ret, option)
    elif xtype in [list]:
        if len(item) == 0:
            ret[key] = ""
        else:
            ret[key] = json.dumps(item, sort_keys=True, ensure_ascii = False)
    else:
        ret[key] = item

    return ret




if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s][%(asctime)s][%(module)s][%(funcName)s][%(lineno)s] %(message)s', level=logging.INFO)
    logging.getLogger("requests").setLevel(logging.WARNING)

    optional_params = {
        '--filename': 'input filename',
        '--outdir': 'output dir'
    }
    main_subtask(__name__, optional_params=optional_params)

"""

    python kgtool/core.py task_download2summary --filename=local/public/eastmoney/price_eastmoney/normal/price_eastmoney_tzzh_all_20170918full.json

"""
