#!/usr/bin/env python

"""

py2neo - Python library for accessing Neo4j via REST interface

---

Copyright 2011 Three Steps Beyond LLP

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

neo4j.py

"""

import rest


class Direction:

	BOTH     = 'all'
	INCOMING = 'incoming'
	OUTGOING = 'outgoing'


class ReturnFilter:

	ALL                = 'all'
	ALL_BUT_START_NODE = 'all_but_start_node'


class GraphDatabaseService(rest.Resource):

	def __init__(self, uri, http=None):
		rest.Resource.__init__(self, uri, http=http)

	def create_node(self, properties=None):
		return Node(self._post(self._lookup('node'), properties), http=self._http)

	def get_reference_node(self):
		return Node(self._lookup('reference_node'), http=self._http)

	def get_relationship_types(self):
		return self._get(self._lookup('relationship_types'))

	def get_node_indexes(self):
		indexes = self._get(self._lookup('node_index'))
		return dict([
			(index, NodeIndex(indexes[index]['template'], http=self._http))
			for index in indexes
		])

	def get_relationship_indexes(self):
		indexes = self._get(self._lookup('relationship_index'))
		return dict([
			(index, RelationshipIndex(indexes[index]['template'], http=self._http))
			for index in indexes
		])


class PropertyContainer(rest.Resource):

	def __init__(self, uri, http=None):
		rest.Resource.__init__(self, uri, http=http)

	def set_properties(self, properties):
		self._put(self._lookup('properties'), properties)

	def get_properties(self):
		return self._get(self._lookup('properties'))

	def remove_properties(self):
		self._delete(self._lookup('properties'))

	def __setitem__(self, key, value):
		self._put(self._lookup('property').format(key=key), value)

	def __getitem__(self, key):
		return self._get(self._lookup('property').format(key=key))

	def __delitem__(self, key):
		self._delete(self._lookup('property').format(key=key))


class Node(PropertyContainer):

	def __init__(self, uri, http=None):
		PropertyContainer.__init__(self, uri, http=http)
		self._id = int('0' + uri.rpartition('/')[-1])

	def __str__(self):
		return "(%d)" % self._id

	def delete(self):
		self._delete(self._index['self'])

	def create_relationship_to(self, other_node, type, data=None):
		return Relationship(self._post(self._lookup('create_relationship'), {
			'to': str(other_node),
			'type': type,
			'data': data
		}), http=self._http)

	def get_relationships(self, direction, *types):
		if len(types) == 0:
			uri = self._lookup(direction + '_relationships')
		else:
			uri = self._lookup(direction + '_typed_relationships').replace('{-list|&|types}', '&'.join(types))
		return [
			Relationship(rel['self'], http=self._http)
			for rel in self._get(uri)
		]

	def get_related_nodes(self, direction, *types):
		if len(types) == 0:
			uri = self._lookup(direction + '_relationships')
		else:
			uri = self._lookup(direction + '_typed_relationships').replace('{-list|&|types}', '&'.join(types))
		return [
			Node(rel['start'] if rel['end'] == self._uri else rel['end'], http=self._http)
			for rel in self._get(uri)
		]

	def get_traverser(self):
		return Traverser(self._lookup('traverse').format(returnType='path'), http=self._http)


class Relationship(PropertyContainer):

	def __init__(self, uri, http=None):
		PropertyContainer.__init__(self, uri, http=http)
		self._id = int('0' + uri.rpartition('/')[-1])
		self.type = self._lookup('type')
		self.data = self._lookup('data')

	def __str__(self):
		return "-[:%s]->" % self.type

	def delete(self):
		self._delete(self._lookup('self'))

	def get_start_node(self):
		return Node(self._lookup('start'), http=self._http)

	def get_end_node(self):
		return Node(self._lookup('end'), http=self._http)


class Path:

	def __init__(self, nodes, relationships):
		self._nodes = nodes
		self._relationships = relationships

	def __str__(self):
		s = ""
		for i in range(len(self._relationships)):
			s += str(self._nodes[i]) + str(self._relationships[i])
		s += str(self._nodes[-1])
		return s

	def __len__(self):
		return len(self._relationships)

	def get_nodes(self):
		return self._nodes

	def get_relationships(self):
		return self._relationships

	def get_start_node(self):
		return self._nodes[0]

	def get_end_node(self):
		return self._nodes[-1]

	def get_last_relationship(self):
		return self._relationships[-1] if len(self._relationships) > 0 else None


class Index(rest.Resource):

	def __init__(self, uri, http=None):
		rest.Resource.__init__(self, uri, http=http)

	def _search(self, key, value):
		return self._get(self._uri.format(key=key, value=value))

	def add(self, entity, key, value):
		self._post(self._uri.format(key=key, value=value), entity._uri)


class NodeIndex(Index):

	def search(self, key, value):
		return [
			Node(item['self'], http=self._http)
			for item in self._search(key, value)
		]


class RelationshipIndex(Index):

	def search(self, key, value):
		return [
			Relationship(item['self'], http=self._http)
			for item in self._search(key, value)
		]


class Traverser(rest.Resource):

	class Order:

		BREADTH_FIRST = 'breadth_first'
		DEPTH_FIRST   = 'depth_first'

	def __init__(self, uri, http=None):
		rest.Resource.__init__(self, uri, http=http)
		self._criteria = {
			'order': Traverser.Order.DEPTH_FIRST,
			'uniqueness': 'node_path'
		}

	def set_max_depth(self, max_depth):
		if 'prune_evaluator' in self._criteria:
			del self._criteria['prune_evaluator']
		self._criteria['max_depth'] = max_depth

	def set_prune_evaluator(self, language, body):
		if 'max_depth' in self._criteria:
			del self._criteria['max_depth']
		self._criteria['prune_evaluator'] = {
			'language': language,
			'body': body
		}

	def set_return_filter(self, language, name):
		self._criteria['return_filter'] = {
			'language': language,
			'name': name
		}

	def add_relationship(self, type, direction=None):
		if 'relationships' not in self._criteria:
			self._criteria['relationships'] = []
		if direction:
			self._criteria['relationships'].append({
				'type': type,
				'direction': direction
			})
		else:
			self._criteria['relationships'].append({
				'type': type
			})

	def remove_relationship(self, type):
		if 'relationships' in self._criteria:
			self._criteria['relationships'] = [
				item
				for item in self._criteria['relationships']
				if item['type'] != type
			]
			if self._criteria['relationships'] == []:
				del self._criteria['relationships']

	def traverse(self, order):
		self._criteria['order'] = order
		return [
			Path([
				Node(uri)
				for uri in path['nodes']
			], [
				Relationship(uri)
				for uri in path['relationships']
			])
			for path in self._post(self._uri, self._criteria)
		]

	def traverse_depth_first(self):
		return self.traverse(Traverser.Order.DEPTH_FIRST)

	def traverse_breadth_first(self):
		return self.traverse(Traverser.Order.BREADTH_FIRST)

