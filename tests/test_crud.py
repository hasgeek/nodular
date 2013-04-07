# -*- coding: utf-8 -*-

import unittest
from nodular import Node, NodePublisher, NodeView, NodeRegistry
from .test_db import db, TestDatabaseFixture
from .test_nodetree import TestType


class MyNodeView(NodeView):
    @NodeView.route('/')
    def index(self):
        return "node-index"


class TestNodeCrud(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeCrud, self).setUp()

        self.registry = NodeRegistry()
        self.registry.register_node(Node, child_nodetypes=['*'])
        self.registry.register_node(TestType, child_nodetypes=['*'], parent_nodetypes=['*'])

        # Make some nodes
        self.root = Node(name=u'root', title=u'Root Node')
        if not hasattr(self, 'nodetype'):
            self.nodetype = Node
        self.node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        self.node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=self.root)
        self.node3 = self.nodetype(name=u'node3', title=u'Node 3', parent=self.node2)
        self.node4 = self.nodetype(name=u'node4', title=u'Node 4', parent=self.node3)
        self.node5 = self.nodetype(name=u'node5', title=u'Node 5', parent=self.root)
        db.session.add_all([self.root, self.node1, self.node2, self.node3, self.node4, self.node5])
        db.session.commit()

        self.rootpub = NodePublisher(u'/')
        self.nodepub = NodePublisher(u'/node2', u'/')

    # def test_publishview(self):
    #     """Publish a default view."""
    #     response = self.rootpub.publish(u'/node2', registry)
    #     self.assertEqual(response, 'node-index')


class TestTypeCrud(TestNodeCrud):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeCrud, self).setUp()
