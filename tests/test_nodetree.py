# -*- coding: utf-8 -*-

import unittest
from sqlalchemy.exc import IntegrityError
from nodular import Node, NodeMixin
from .test_db import db, TestDatabaseFixture


class TestType(NodeMixin, Node):
    __tablename__ = u'test_type'
    content = db.Column(db.Unicode(250), nullable=False, default=u'test')


class TestNodeTree(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeTree, self).setUp()
        self.root = Node(name=u'root', title=u'Root Node')
        if not hasattr(self, 'nodetype'):  # See TestType tests below
            self.nodetype = Node
        db.session.add(self.root)

    def test_double_root(self):
        """
        There can be only one root node in the database.
        The second one will have a duplicate / path.
        """
        root2 = self.nodetype(name=u'node', title=u'Root Node 2')
        db.session.add(root2)
        self.assertRaises(IntegrityError, db.session.commit)

    def test_node_name_conflict(self):
        """
        Two nodes cannot have the same name if they share a parent.
        """
        node1 = self.nodetype(name=u'node', title=u'Node 1', user=self.user1, parent=self.root)
        node2 = self.nodetype(name=u'node', title=u'Node 2', user=self.user1, parent=self.root)
        db.session.add(node1)
        db.session.add(node2)
        self.assertRaises(IntegrityError, db.session.commit)

    def test_node_invalid_name(self):
        """
        Node names cannot be empty, cannot have slashes and cannot have trailing spaces.
        """
        self.assertRaises(ValueError, self.nodetype, title=u'Node 1', parent=self.root,
            name=None)
        self.assertRaises(ValueError, self.nodetype, title=u'Node 1', parent=self.root,
            name=u'')
        self.assertRaises(ValueError, self.nodetype, title=u'Node 1', parent=self.root,
            name=u' ')
        self.assertRaises(ValueError, self.nodetype, title=u'Node 1', parent=self.root,
            name=u'/node1')
        node1 = self.nodetype(name='node ', title=u'Node 1', parent=self.root)
        self.assertEqual(node1.name, 'node')
        node1.name = ' node '
        self.assertEqual(node1.name, 'node')
        node1.name = ' node'
        self.assertEqual(node1.name, 'node')

    def test_auto_add_to_session(self):
        """
        Nodes are automatically added to the session if they have a parent
        that is in the database or in the session.
        """
        node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=node1)
        node3 = self.nodetype(name=u'node3', title=u'Node 3')
        db.session.commit()
        self.assertNotEqual(node1.id, None)
        self.assertNotEqual(node2.id, None)
        self.assertNotEqual(node1.id, node2.id)
        self.assertEqual(node3.id, None)

    def test_node_reparent(self):
        """
        Changing a node's parent should update NodeTree
        """
        node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=self.root)
        node3 = self.nodetype(name=u'node3', title=u'Node 3', parent=self.root)
        node4 = self.nodetype(name=u'node4', title=u'Node 4', parent=node2)
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

    def test_rename_path(self):
        """
        Test that renaming a node will recursively amend paths of children.
        """
        node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=node1)
        node3 = self.nodetype(name=u'node3', title=u'Node 3', parent=self.root)
        node4 = self.nodetype(name=u'node4', title=u'Node 4', parent=node2)
        db.session.add_all([node1, node2, node3, node4])
        db.session.commit()

        self.assertEqual(self.root.path, u'/')
        self.assertEqual(node1.path, u'/node1')
        self.assertEqual(node2.path, u'/node1/node2')
        self.assertEqual(node3.path, u'/node3')
        self.assertEqual(node4.path, u'/node1/node2/node4')

        node2.rename(u'nodeX')

        self.assertEqual(node2.name, u'nodeX')
        self.assertEqual(self.root.path, u'/')
        self.assertEqual(node1.path, u'/node1')
        self.assertEqual(node2.path, u'/node1/nodeX')
        self.assertEqual(node3.path, u'/node3')
        self.assertEqual(node4.path, u'/node1/nodeX/node4')

    def test_rename_alias(self):
        """
        Test that renaming a node will create a NodeAlias instance.
        """
        node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=self.root)
        db.session.add_all([node1, node2])
        db.session.commit()

        self.assertEqual(self.root.path, u'/')
        self.assertEqual(node1.path, u'/node1')
        self.assertEqual(node2.path, u'/node2')

        self.assertEqual(len(node1.parent.aliases), 0)
        node1.rename(u'nodeX')
        db.session.commit()
        self.assertEqual(len(node1.parent.aliases), 1)
        self.assertEqual(node1.parent.aliases[u'node1'].node, node1)

        node2.rename(u'node1')
        db.session.commit()
        # Aliases aren't removed when the name is used again
        self.assertEqual(len(node1.parent.aliases), 2)
        self.assertEqual(node2.parent.aliases[u'node2'].node, node2)
        self.assertEqual(node1.parent.aliases[u'node1'].node, node1)

        node2.rename(u'nodeY')
        db.session.commit()
        # But when the new name also moves out of the way, the alias is updated
        self.assertEqual(len(node1.parent.aliases), 2)
        self.assertEqual(node1.parent.aliases[u'node1'].node, node2)
        self.assertEqual(node1.parent.aliases[u'node2'].node, node2)

    def test_long_path(self):
        """
        Test that having really long names will cause path to fail gracefully.
        """
        node1 = self.nodetype(name=u'1' * 250, title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'2' * 250, title=u'Node 2', parent=node1)
        node3 = self.nodetype(name=u'3' * 250, title=u'Node 3', parent=node2)

        self.assertRaises(ValueError, self.nodetype, name=u'4' * 250, title=u'Node 4', parent=node3)

        node4 = self.nodetype(name=u'4' * 200, title=u'Node 4', parent=node3)
        node5 = self.nodetype(name=u'5' * 200, title=u'Node 5', parent=self.root)

        self.assertRaises(ValueError, setattr, node4, 'name', '4' * 250)
        self.assertRaises(ValueError, setattr, node5, 'parent', node4)


class TestNodeDict(TestDatabaseFixture):
    """Dictionary access to node hierarchy."""
    def setUp(self):
        super(TestNodeDict, self).setUp()
        # Make some nodes
        self.root = Node(name=u'root', title=u'Root Node')
        if not hasattr(self, 'nodetype'):
            self.nodetype = Node
        self.node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        self.node2 = Node(name=u'node2', title=u'Node 2', parent=self.root)
        self.node3 = self.nodetype(name=u'node3', title=u'Node 3', parent=self.node2)
        self.node4 = self.nodetype(name=u'node4', title=u'Node 4', parent=self.node3)
        self.node5 = self.nodetype(name=u'node5', title=u'Node 5', parent=self.root)
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


class TestTypeTree(TestNodeTree):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeTree, self).setUp()


class TestTypeDict(TestNodeDict):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeDict, self).setUp()

    def test_type(self):
        self.assertEqual(self.root.type, u'node')
        self.assertEqual(self.node1.type, u'test_type')
        self.assertEqual(self.node2.type, u'node')
        self.assertEqual(self.node3.type, u'test_type')
        self.assertEqual(self.node4.type, u'test_type')
        self.assertEqual(self.node5.type, u'test_type')


if __name__ == '__main__':
    unittest.main()
