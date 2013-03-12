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

    def test_reparent_node(self):
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

if __name__ == '__main__':
    unittest.main()
