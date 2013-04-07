# -*- coding: utf-8 -*-

import unittest
from nodular import Node, NodeView, NodePublisher, NodeRegistry
from .test_db import db, TestDatabaseFixture
from .test_nodetree import TestType


class MyNodeView(NodeView):
    @NodeView.route('/')
    def index(self):
        return u"node-index"

    def dummy(self):
        pass


class ExpandedNodeView(MyNodeView):
    @NodeView.route('/')
    def index(self):
        # This never gets called because MyNodeView.index is registered first
        return u'expanded-index'

    @NodeView.route('/edit', methods=['GET'])
    def editget(self):
        return u'edit-GET'

    @NodeView.route('/edit', methods=['POST'])
    def editpost(self):
        return u'edit-POST'

    @NodeView.route('/multimethod', methods=['GET', 'POST'])
    def multimethod(self):
        from flask import request
        return u'multimethod-' + request.method


class TestNodeView(unittest.TestCase):
    def test_view_route(self):
        """Test that NodeView.route defines a route."""
        self.assertTrue(hasattr(MyNodeView, 'url_map'))
        self.assertEqual(type(MyNodeView.index), type(MyNodeView.dummy))
        self.assertEqual(len(list(MyNodeView.url_map.iter_rules())), 1)


class TestNodeViews(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeViews, self).setUp()

        self.registry = NodeRegistry()
        self.registry.register_node(Node, view=MyNodeView, child_nodetypes=['*'])
        self.registry.register_node(TestType, view=MyNodeView, child_nodetypes=['*'], parent_nodetypes=['*'])

        self.registry.register_view('node', ExpandedNodeView)
        self.registry.register_view('test_type', ExpandedNodeView)

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

        self.rootpub = NodePublisher(self.registry, u'/')
        self.nodepub = NodePublisher(self.registry, u'/node2', u'/')

    def test_publishview(self):
        """Publish a default view."""
        with self.app.test_request_context():
            response = self.rootpub.publish(u'/node2')
        self.assertEqual(response, 'node-index')

    def test_methods(self):
        """Publish views with different methods."""
        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertEqual(response, 'edit-GET')

        with self.app.test_request_context(method='POST'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertEqual(response, 'edit-POST')

        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-GET')

        with self.app.test_request_context(method='POST'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-POST')


class TestTypeViews(TestNodeViews):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeViews, self).setUp()