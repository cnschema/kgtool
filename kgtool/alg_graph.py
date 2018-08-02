#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Qiu Minghao

class DirectedGraphNode:
   def __init__(self, data):
       self.data = data
       self.links = []

   def pointsTo(self, node):
       self.links.append(node)

class DirectedGraph:
   def __init__(self, graph):
       self.nodes = []
       self.nodeCount = 0
       self.relation = {}
       dct = {}
       for each in graph:
           node, link = each[0], each[1]
           if not dct.has_key(node):
               dct[node] = self.newNode(node)
           if not dct.has_key(link):
               dct[link] = self.newNode(link)
           dct[node].pointsTo(dct[link])

       for node, link in dct.items():
           self.relation[node] = list(set(self.getchild(dct[node].data,dct)+[node]))

   def getchild(self,name,dct):
       if len(dct[name].links)>0:
           for each in dct[name].links:
               return [each.data]+self.getchild(each.data,dct)
       else:
           return []

   def newNode(self, data):
       node = DirectedGraphNode(data)
       self.nodes.append(node)
       self.nodeCount += 1
       return node
