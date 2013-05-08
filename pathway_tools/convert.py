#!/usr/bin/env python

import networkx
from xml.dom.minidom import Document
import xml.sax
import sys
import csv
import os
from glob import glob

class FormatException(Exception):
    pass

def read_sif(handle):
    gr = networkx.MultiDiGraph()
    for line in handle:
        tmp = line.rstrip().split("\t")
        gr.add_edge(tmp[0], tmp[2], interaction=tmp[1])
    return gr

def write_sif(gr, handle, edge_type_field='interaction'):
    for (e1,e2,data) in gr.edges_iter(data=True):
        interaction = data.get(edge_type_field, "pp")
        handle.write("%s\t%s\t%s\n" % (e1, interaction, e2))

def read_paradigm_graph(handle):
    gr = networkx.MultiDiGraph()
    for line in handle:
        tmp = line.rstrip().split("\t")
        if len(tmp) == 2:
            if tmp[1] in gr.node:
                raise FormatException("Duplicate element declaration for : %s" % (tmp[1]))                
            gr.add_node( tmp[1], type=tmp[0] )
        elif len(tmp) == 3:
            if tmp[0] not in gr.node:
                raise FormatException("Missing element declaration for : %s" % (tmp[0]))
            if tmp[1] not in gr.node:
                raise FormatException("Missing element declaration for : %s" % (tmp[1]))
            gr.add_edge(tmp[0], tmp[1], interaction=tmp[2])
        else:
            raise FormatException("Bad line: %s" % (line))
    return gr

def write_paradigm_graph(gr, handle, node_type_field='type', node_type_default='protein', edge_type_field='interaction', edge_type_default='-a>'):
    for e in sorted(gr.node):
        handle.write("%s\t%s\n" % (gr.node[e].get(node_type_field, node_type_default), e))

    for src in gr.edge:
        for dst in gr.edge[src]:
            for edge in gr.edge[src][dst]:
                handle.write("%s\t%s\t%s\n" % (src, dst, gr.edge[src][dst][edge].get(edge_type_field, edge_type_default)))


def load_paradigm_dir(base_dir):
    pid_names = {}
    handle = open(os.path.join(base_dir, "names.tab"))
    for line in handle:
        tmp = line.rstrip().split("\t")
        pid_names[tmp[0]] = [  
            unicode(tmp[1], 'ascii', errors="ignore"), 
            unicode(tmp[2], 'ascii', errors="ignore")
        ]   
    handle.close()
    gr = networkx.MultiDiGraph()
    for a in glob(os.path.join(base_dir, "pid*.tab")):
        pid_name = os.path.basename(a).split("_")[1]
        handle = open(a)
        for line in handle:
            tmp = line.rstrip().split("\t")
            if len(tmp) == 2:
                if tmp[1] not in gr.node:
                    gr.add_node( tmp[1], { 'type' : tmp[0], 'pathway' : [] } )
                gr.node[tmp[1]]['pathway'].append( pid_names[pid_name][0] )
            elif len(tmp) == 3:
                gr.add_edge(tmp[0], tmp[1], interaction=tmp[2])
        handle.close()
    return gr


def write_xgmml(gr, handle):
    doc = Document()
    graph_node = doc.createElement('graph')
    graph_node.setAttribute("xmlns", "http://www.cs.rpi.edu/XGMML")


    graph_node.setAttribute("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    graph_node.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink" )
    graph_node.setAttribute("xmlns:rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#" )
    graph_node.setAttribute("xmlns:cy", "http://www.cytoscape.org" )
    graph_node.setAttribute("directed", "1")
    doc.appendChild(graph_node)

    name_map = {}
    for i, n in enumerate(gr.node):
        name_map[n] = i
        node = doc.createElement('node')
        node.setAttribute('label', str(n))
        node.setAttribute('id', str(i))
        for key, value in gr.node[n].items():
            att_node = doc.createElement('att')
            att_node.setAttribute('name', str(key))
            if type(value) == float:
                att_node.setAttribute('value', str(value))
                att_node.setAttribute('type', "real")
            elif type(value) == int:
                att_node.setAttribute('value', str(value))
                att_node.setAttribute('type', "integer")
            elif type(value)== list:
                att_node.setAttribute('type', "list")
                for elm in value:
                    list_node = doc.createElement("att")
                    list_node.setAttribute("name", str(key))
                    list_node.setAttribute('value', str(elm))
                    if type(elm) == float:
                        list_node.setAttribute("type", "real")
                    elif type(elm) == int:
                        list_node.setAttribute("type", "integer")
                    else:
                        list_node.setAttribute("type", "string")
                    att_node.appendChild(list_node)
            else:
                att_node.setAttribute('value', str(value))
                att_node.setAttribute('type', "string")
            node.appendChild(att_node)
        graph_node.appendChild(node)

    for source in gr.edge:
        for target in gr.edge[source]:
            for edge in gr.edge[source][target]:
                edge_node = doc.createElement("edge")
                edge_node.setAttribute("label", "%s - %s" % (source, target))
                edge_node.setAttribute("source", str(name_map[source]))
                edge_node.setAttribute("target", str(name_map[target]))
                for key, value in gr.edge[source][target][edge].items():
                    att_node = doc.createElement('att')
                    att_node.setAttribute('name', key)
                    att_node.setAttribute('value', str(value))
                    if type(value) == float:
                        att_node.setAttribute('type', "real")
                    elif type(value) == int:
                        att_node.setAttribute('type', "integer")
                    else:
                        att_node.setAttribute('type', "string")
                    edge_node.appendChild(att_node)
                graph_node.appendChild(edge_node)

    doc.writexml(handle, addindent=" ", newl="\n")

class GraphComp:
    def __init__(self, parser, attrs):
        self.graph = networkx.MultiDiGraph()

    def add_att(self, name, value):
        self.graph.graph[name] =  value

    def pop(self):
        return self.graph

class NodeComp:
    def __init__(self, parser, parent, attrs):
        self.label = attrs.getValue('label')
        self.parser = parser
        self.parent = parent
        parser.id_map[attrs.getValue('id')] = self.label
        parent.graph.add_node( self.label )

    def add_att(self, name, value):
        self.parent.graph.node[self.label][name] =  value

    def pop(self):
        pass


class EdgeComp:
    def __init__(self, parser, parent, attrs):
        self.parent = parent
        self.src = parser.id_map[attrs.getValue('source')]
        self.target = parser.id_map[attrs.getValue('target')]
        self.key = 0
        if self.target in parent.graph.edge[self.src]:
            self.key=len(parent.graph.edge[self.src][self.target])
        parent.graph.add_edge(self.src,self.target)

    def add_att(self, name, value):
        self.parent.graph.edge[self.src][self.target][self.key][name] =  value

    def pop(self):
        pass


class AttComp:
    def __init__(self, parser, parent, attrs):
        self.parent = parent
        self.name = attrs.getValue('name')
        if attrs.has_key('value'):
            parent.add_att(attrs.getValue('name'), attrs.getValue('value'))
        self.att_list = None
        if attrs.has_key('type') and attrs.getValue("type") == "list":
            self.att_list = []

    def add_att(self, name, value):
        self.att_list.append( value )

    def pop(self):
        if self.att_list is not None:
            self.parent.add_att(self.name, self.att_list)


class XGMMLHandler(xml.sax.ContentHandler):
    def __init__(self):
        xml.sax.ContentHandler.__init__(self)
        self.elem_stack = []
        self.id_map = {}
        self.last_value = None

    def startElement(self, name, attrs):
        #print("startElement '" + name + "'")
        if name == "graph":
            self.elem_stack.append(GraphComp(self, attrs))
        elif name == 'node':
            self.elem_stack.append(NodeComp(self, self.elem_stack[-1], attrs))
        elif name == 'edge':
            self.elem_stack.append(EdgeComp(self, self.elem_stack[-1], attrs))
        elif name == 'att':
            self.elem_stack.append(AttComp(self, self.elem_stack[-1], attrs))
        else:
            self.elem_stack.append(None)
            
 
    def endElement(self, name):
        last_node = self.elem_stack.pop()
        if last_node is not None:
            self.last_value = last_node.pop()

    def result(self):
        return self.last_value



def read_xgmml(handle):
    handler = XGMMLHandler()
    xml.sax.parse(handle, handler)
    return handler.result()



def write_binary_matrix(gr, handle, postive="1", negative="0", delimiter="\t", nodelist=None):
    if nodelist is None:
        nodelist = gr.node

    writer = csv.writer(handle, delimiter=delimiter, lineterminator="\n")
    for s in nodelist:
        out = []
        for t in nodelist:
            if s in gr.edge and t in gr.edge[s]:
                out.append(postive)
            else:
                out.append(negative)
        writer.writerow(out)



