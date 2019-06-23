#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Li Ding


"""
shared code without external dependency
"""

import collections
import copy
from kgtool.core import *  # noqa


def gen_cns_link_default_primary_key(cns_item):
    assert cns_item["@type"]
    assert isinstance(cns_item["@type"], list)
    assert "CnsLink" in cns_item["@type"]
    assert "in" in cns_item
    assert "out" in cns_item
    ret = [cns_item["@type"][0]]
    for p in ["in", "out", "date", "identifier", "startDate", "endDate"]:
        ret.append(cns_item.get(p, ""))
    # logging.info(ret)
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


class CnsBugReport():

    def __init__(self):
        self.data = {   "bugs": [],
                        "bugs_sample": {},
                        "xtemplate":collections.Counter(),
                        "stats": collections.Counter(),
                        "flag_detail": False }


    def report_bug(self, bug):
        key = r" | ".join([bug["category"], bug["description"], bug.get("class", ""), bug.get("property", "")])
        self.data["stats"][key] += 1
        if key not in self.data["bugs_sample"]:
            self.data["bugs_sample"][key] = copy.deepcopy(bug)

        if self.data.get("flag_detail"):
            msg = json.dumps(bug, ensure_ascii=False, sort_keys=True)
            self.data["bugs"].append(bug)
            logging.info(msg)

    def has_bug(self):
        return len(self.data["bugs_sample"]) > 0
