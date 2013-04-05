# -*- coding: utf-8 -*-

import unittest
from nodular import NodeView
from nodular.registry import dottedname
from .test_db import TestDatabaseFixture
from .test_nodetree import TestType


class TestDottedName(unittest.TestCase):
    """Test dottedname"""
    def test_dottedname(self):
        self.assertEqual(dottedname(TestDottedName), 'tests.test_registry.TestDottedName')
        self.assertEqual(dottedname(NodeView), 'nodular.crud.NodeView')
        self.assertEqual(dottedname(TestType), 'tests.test_nodetree.TestType')


class TestRegistry(TestDatabaseFixture):
    """Test the node registry."""
    pass

if __name__ == '__main__':
    unittest.main()
