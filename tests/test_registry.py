# -*- coding: utf-8 -*-

import unittest
from nodular import Node, NodeRegistry
from nodular.registry import dottedname
from .test_db import TestDatabaseFixture
from .test_nodetree import TestType
from .test_publish_view import MyNodeView


class TestDottedName(unittest.TestCase):
    """Test dottedname"""
    def test_dottedname(self):
        self.assertEqual(dottedname(TestDottedName), 'tests.test_registry.TestDottedName')
        self.assertEqual(dottedname(MyNodeView), 'tests.test_publish_view.MyNodeView')
        self.assertEqual(dottedname(TestType), 'tests.test_nodetree.TestType')


class TestRegistry(TestDatabaseFixture):
    """Test the node registry."""
    def setUp(self):
        super(TestRegistry, self).setUp()
        self.registry = NodeRegistry()

    def test_init_registry(self):
        """Initializing a registry gives it some standard attributes."""
        for attr in ['nodes', 'child_nodetypes', 'nodeviews', 'viewlist', 'urlmaps']:
            # The attribute exists
            self.assertTrue(hasattr(self.registry, attr))
            # The attribute is a dict
            self.assertTrue(isinstance(getattr(self.registry, attr), dict))
            # The dict is initially empty
            self.assertEqual(len(getattr(self.registry, attr)), 0)

    def test_register_node_without_view(self):
        """Nodes can be registered without a view."""
        self.registry.register_node(Node)
        self.assertEqual(len(self.registry.nodes), 1)
        self.assertEqual(len(self.registry.nodeviews), 0)
        self.assertTrue(Node.__type__ in self.registry.nodes)
        self.registry.register_node(TestType)
        self.assertEqual(len(self.registry.nodes), 2)
        self.assertEqual(len(self.registry.nodeviews), 0)
        self.assertTrue(TestType.__type__ in self.registry.nodes)

    def test_register_node_with_view(self):
        """Nodes can be registered with a view."""
        self.registry.register_node(Node, view=MyNodeView)
        self.assertEqual(len(self.registry.nodes), 1)
        self.assertEqual(len(self.registry.nodeviews), 1)
        self.assertTrue(Node.__type__ in self.registry.nodes)
        self.registry.register_node(TestType, view=MyNodeView)
        self.assertEqual(len(self.registry.nodes), 2)
        self.assertEqual(len(self.registry.nodeviews), 2)
        self.assertTrue(TestType.__type__ in self.registry.nodes)

    def test_register_itype_with_view(self):
        """Nodes can be registered with an instance type."""
        self.registry.register_node(Node, itype='home', title='Home page', view=MyNodeView)
        self.assertEqual(len(self.registry.nodes), 1)
        self.assertEqual(len(self.registry.nodeviews), 1)
        self.assertEqual(self.registry.nodes['home'].model, Node)
        self.assertFalse(Node.__type__ in self.registry.nodes)
        self.assertTrue('home' in self.registry.nodes)
        self.assertTrue(MyNodeView in self.registry.nodeviews['home'])
        self.assertFalse(MyNodeView in self.registry.nodeviews[Node.__type__])
