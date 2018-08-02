#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Qiu Minghao
import collections

class DirectedGraph:
    def __init__(self, arc_list):
        self.nodes = collections.defaultdict(list)
        node_from_list = set()
        node_to_list = set()
        for arc in arc_list:
           node_from, node_to = arc
           self.nodes[node_from].append( node_to )
           self.nodes[node_to].extend( [] )

           node_from_list.add( node_from )
           node_to_list.add( node_to )

        self.roots = node_from_list.difference( node_to_list )

    def _dfs(self, node, path, subtree):
        """
            run depth first search
        """
        for element in path:
            subtree[element].append(node)

        for child in self.nodes[node]:
            if child in path:
                continue
            if child == node:
                continue

            path_child = [node]
            path_child.extend(path)
            self._dfs(child, path_child, subtree)

    def compute_subtree(self, include_self=True):
        """
            problem is defined here
            https://www.geeksforgeeks.org/sub-tree-nodes-tree-using-dfs/
        """
        subtree = collections.defaultdict(list)
        if include_self:
            for node in self.nodes:
                subtree[node] = [node]

        for root in self.roots:
           self._dfs(root, [], subtree)

        return subtree
