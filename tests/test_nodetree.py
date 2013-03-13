# -*- coding: utf-8 -*-

import unittest
from sqlalchemy.exc import IntegrityError
from nodular import Node
from .test_db import db, TestDatabaseFixture


class TestNodeTree(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeTree, self).setUp()
        self.root = Node(name=u'root', title=u'Root Node')
        db.session.add(self.root)

    def test_double_root(self):
        """
        There can be only one root node in the database.
        The second one will have a duplicate / path.
        """
        root2 = Node(name=u'node', title=u'Root Node 2')
        db.session.add(root2)
        self.assertRaises(IntegrityError, db.session.commit)

    def test_parented_node_name_conflict(self):
        """
        Two nodes cannot have the same name if they share a parent.
        """
        node1 = Node(name=u'node', title=u'Node 1', user=self.user1, parent=self.root)
        node2 = Node(name=u'node', title=u'Node 2', user=self.user1, parent=self.root)
        db.session.add(node1)
        db.session.add(node2)
        self.assertRaises(IntegrityError, db.session.commit)

    def test_auto_add_to_session(self):
        """
        Nodes are automatically added to the session if they have a parent
        that is in the database or in the session.
        """
        node1 = Node(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = Node(name=u'node2', title=u'Node 2', parent=node1)
        node3 = Node(name=u'node3', title=u'Node 3')
        db.session.commit()
        self.assertNotEqual(node1.id, None)
        self.assertNotEqual(node2.id, None)
        self.assertNotEqual(node1.id, node2.id)
        self.assertEqual(node3.id, None)

    def test_node_reparent(self):
        """
        Changing a node's parent should update NodeTree
        """
        node1 = Node(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = Node(name=u'node2', title=u'Node 2', parent=self.root)
        node3 = Node(name=u'node3', title=u'Node 3', parent=self.root)
        node4 = Node(name=u'node4', title=u'Node 4', parent=node2)
        db.session.add_all([node1, node2, node3, node4])
        db.session.commit()

        self.assertEqual(self.root.path, u'/')
        self.assertEqual(node1.path, u'/node1')
        self.assertEqual(node2.path, u'/node2')
        self.assertEqual(node3.path, u'/node3')
        self.assertEqual(node4.path, u'/node2/node4')

        node2.parent = node1
        db.session.commit()

        self.assertEqual(self.root.path, u'/')
        self.assertEqual(node1.path, u'/node1')
        self.assertEqual(node2.path, u'/node1/node2')
        self.assertEqual(node3.path, u'/node3')
        self.assertEqual(node4.path, u'/node1/node2/node4')


class TestNodeDict(TestDatabaseFixture):
    """Dictionary access to node hierarchy."""
    def setUp(self):
        super(TestNodeDict, self).setUp()
        # Make some nodes
        self.root = Node(name=u'root', title=u'Root Node')
        self.node1 = Node(name=u'node1', title=u'Node 1', parent=self.root)
        self.node2 = Node(name=u'node2', title=u'Node 2', parent=self.root)
        self.node3 = Node(name=u'node3', title=u'Node 3', parent=self.node2)
        self.node4 = Node(name=u'node4', title=u'Node 4', parent=self.node3)
        self.node5 = Node(name=u'node5', title=u'Node 5', parent=self.root)
        db.session.add_all([self.root, self.node1, self.node2, self.node3, self.node4, self.node5])
        db.session.commit()

    def test_getitem(self):
        """Test __getitem__"""
        self.assertEqual(self.node4, self.root.nodes[u'node2'].nodes[u'node3'].nodes[u'node4'])
        self.assertRaises(KeyError, self.root.nodes.__getitem__, u'node3')

    def test_contains(self):
        """Test __contains__"""
        self.assertTrue(u'node1' in self.root.nodes)
        self.assertFalse(u'node3' in self.root.nodes)
        self.assertTrue(u'node3' in self.node2.nodes)
        self.assertTrue(u'node4' in self.node3.nodes)

    def test_iter(self):
        """Test __iter__"""
        self.assertEqual(set(self.root.nodes), set(['node1', 'node2', 'node5']))

    def test_setitem(self):
        """Test __setitem__"""
        self.node1.nodes[u'nodeX'] = self.node2
        self.assertEqual(self.node2.name, 'nodeX')
        self.assertEqual(self.node2.parent, self.node1)
        self.assertEqual(self.node2.path, '/node1/nodeX')
        self.assertEqual(self.node3.path, '/node1/nodeX/node3')
        self.assertEqual(self.node4.path, '/node1/nodeX/node3/node4')

    def test_delitem(self):
        """Test __delitem__"""
        self.node1.nodes[u'nodeX'] = self.node2
        db.session.commit()
        del self.node1.nodes[u'nodeX']
        db.session.commit()
        self.assertEqual(set(self.root.nodes), set(['node1', 'node5']))

    def test_length(self):
        """Test __len__"""
        self.assertEqual(len(self.root.nodes), 3)
        self.assertEqual(len(self.node1.nodes), 0)
        self.node1.nodes[u'nodeX'] = self.node2
        db.session.commit()
        self.assertEqual(len(self.root.nodes), 2)
        self.assertEqual(len(self.node1.nodes), 1)

    def test_keys_values(self):
        """Test keys(), values() and items()"""
        self.assertEqual(set(self.root.nodes.keys()), set(['node1', 'node2', 'node5']))
        self.assertEqual(set(self.root.nodes.values()), set([self.node1, self.node2, self.node5]))
        self.assertEqual(set(self.root.nodes.items()),
            set([('node1', self.node1), ('node2', self.node2), ('node5', self.node5)]))

if __name__ == '__main__':
    unittest.main()
