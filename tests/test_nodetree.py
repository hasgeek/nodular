# -*- coding: utf-8 -*-

import unittest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from nodular import Node, NodeMixin, NodeAlias
from nodular.node import Property
from .test_db import db, TestDatabaseFixture


class TestType(NodeMixin, Node):
    __tablename__ = u'test_type'
    content = db.Column(db.Unicode(250), nullable=False, default=u'test')

    def permissions(self, user, inherited=None):
        perms = super(TestType, self).permissions(user, inherited)
        perms.add('view')  # Grant everyone view access
        return perms


class TestNodetype(unittest.TestCase):
    def test_nodetype(self):
        self.assertEqual(Node.__type__, 'node')
        self.assertEqual(TestType.__type__, 'test_type')


class TestNodeTree(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeTree, self).setUp()
        self.root = Node(name=u'root', title=u'Root Node')
        if not hasattr(self, 'nodetype'):  # See TestType tests below
            self.nodetype = Node
        db.session.add(self.root)

    def test_double_root(self):
        """
        There can be more than one root in the database.
        """
        root2 = self.nodetype(name=u'node', title=u'Root Node 2')
        db.session.add(root2)
        db.session.commit()

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

        node2.name = u'nodeX'

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
        node1.name = u'nodeX'
        db.session.commit()
        self.assertEqual(len(node1.parent.aliases), 1)
        self.assertEqual(node1.parent.aliases[u'node1'].node, node1)

        node2.name = u'node1'
        db.session.commit()
        # Aliases aren't removed when the name is used again
        self.assertEqual(len(node1.parent.aliases), 2)
        self.assertEqual(node2.parent.aliases[u'node2'].node, node2)
        self.assertEqual(node1.parent.aliases[u'node1'].node, node1)

        node2.name = u'nodeY'
        db.session.commit()
        # But when the new name also moves out of the way, the alias is updated
        self.assertEqual(len(node1.parent.aliases), 2)
        self.assertEqual(node1.parent.aliases[u'node1'].node, node2)
        self.assertEqual(node1.parent.aliases[u'node2'].node, node2)

    def test_delete_alias(self):
        """
        Test that deleting a node will create a blank NodeAlias instance.
        """
        node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=self.root)
        db.session.add_all([node1, node2])
        db.session.commit()

        self.assertEqual(self.root.path, u'/')
        self.assertEqual(node1.path, u'/node1')
        self.assertEqual(node2.path, u'/node2')

        self.assertEqual(len(self.root.aliases), 0)
        db.session.delete(node1)
        db.session.commit()
        self.assertEqual(len(self.root.aliases), 1)
        self.assertEqual(self.root.aliases[u'node1'].node, None)

        del self.root.nodes[u'node2']
        db.session.commit()

        self.assertTrue(u'node2' in self.root.aliases)
        self.assertEqual(len(self.root.aliases), 2)
        self.assertEqual(self.root.aliases[u'node2'].node, None)

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

    def test_itype(self):
        """
        Test that the instance type value is used to determine the effective type.
        """
        node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=self.root, itype=u'folder')
        db.session.add_all([node1, node2])
        db.session.commit()

        # Test that node1 has an etype of the native node type, while node2 has itype
        self.assertEqual(node1.etype, self.nodetype.__type__)
        self.assertEqual(node2.etype, u'folder')

        # Instance type can be changed at runtime
        node1.itype = u'misc'
        node2.itype = None

        self.assertEqual(node1.etype, u'misc')
        self.assertEqual(node2.etype, self.nodetype.__type__)

        # Setting instance type to a falsy value rewrites it to None
        self.assertEqual(node1.itype, u'misc')
        node1.itype = u''
        self.assertEqual(node1.itype, None)


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
        self.assertEqual(set(self.root.nodes), set(['node1', 'node2', 'node5']))
        self.assertEqual(Node.query.filter_by(name=u'nodeX').first(), None)
        self.assertEqual(Node.query.filter_by(name=u'node2').first(), self.node2)

        self.node1.nodes[u'nodeX'] = self.node2
        db.session.commit()

        self.assertEqual(set(self.root.nodes), set(['node1', 'node5']))
        self.assertEqual(Node.query.filter_by(name=u'nodeX').first(), self.node2)
        self.assertEqual(Node.query.filter_by(name=u'node2').first(), None)

        n2aliases = self.node2.selfaliases
        self.assertNotEqual(len(n2aliases), 0)  # Because of the nodeX assignment above
        del self.node1.nodes[u'nodeX']
        db.session.commit()

        self.assertEqual(set(self.node1.nodes), set([]))
        self.assertEqual(set(self.root.nodes), set(['node1', 'node5']))

        n5aliases = self.node5.selfaliases
        del self.root.nodes[u'node5']
        db.session.commit()

        self.assertEqual(set(self.root.nodes), set(['node1']))

        # Confirm nodes are really deleted
        self.assertEqual(Node.query.filter_by(name=u'nodeX').first(), None)  # deleted
        self.assertEqual(Node.query.filter_by(name=u'node2').first(), None)  # old name
        self.assertEqual(Node.query.filter_by(name=u'node3').first(), None)  # cascaded
        self.assertEqual(Node.query.filter_by(name=u'node4').first(), None)  # cascaded
        self.assertEqual(Node.query.filter_by(name=u'node5').first(), None)  # deleted
        self.assertEqual(Node.query.get(self.node2.id), None)

        # Confirm the aliases are still there and now indicate the node is gone
        for a in n2aliases:
            self.assertEqual(a.node_id, None)
        for a in n5aliases:
            self.assertEqual(a.node_id, None)

        # Confirm that no aliases have been made for child nodes deleted in the cascade
        # Aliases are for nodeX, node2 and node5, but not for node3 and node4
        self.assertEqual(len(NodeAlias.query.all()), 3)

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


class TestProperties(TestDatabaseFixture):
    def setUp(self):
        super(TestProperties, self).setUp()
        # Make some nodes
        self.root = Node(name=u'root', title=u'Root Node')
        if not hasattr(self, 'nodetype'):
            self.nodetype = Node
        self.node1 = self.nodetype(name=u'node1', title=u'Node 1', parent=self.root)
        self.node2 = self.nodetype(name=u'node2', title=u'Node 2', parent=self.root)
        self.node3 = self.nodetype(name=u'node3', title=u'Node 3', parent=self.node2)
        self.node4 = self.nodetype(name=u'node4', title=u'Node 4', parent=self.node3)
        db.session.add_all([self.root, self.node1, self.node2, self.node3, self.node4])
        db.session.commit()

    def test_property_dict(self):
        """Properties behave like a simple dictionary."""
        self.node1.properties[u'prop1'] = u'strvalue'
        # Properties should be retrievable without committing
        self.assertEqual(self.node1.properties.get(u'prop1'), u'strvalue')
        db.session.commit()
        # And retrievable after committing
        self.assertEqual(self.node1.properties.get(u'prop1'), u'strvalue')
        # Properties can be integers
        self.node1.properties[u'prop2'] = 123
        db.session.commit()
        self.assertEqual(self.node1.properties.get(u'prop2'), 123)
        # Properties should be committed to the database
        prop1 = Property.query.get((self.node1.id, u'', u'prop1'))
        prop2 = Property.query.get((self.node1.id, u'', u'prop2'))
        self.assertNotEqual(prop1, None)
        self.assertNotEqual(prop2, None)
        self.assertEqual(prop1.value, u'strvalue')
        self.assertEqual(prop2.value, 123)

    def test_property_namespace_predicate(self):
        """Properties have distinct namespace and predicate"""
        self.node1.properties[u'geo:lat'] = 12.96148
        self.node1.properties[u'geo:lon'] = 77.64431

        db.session.commit()

        prop1 = Property.query.get((self.node1.id, u'geo', u'lat'))
        prop2 = Property.query.get((self.node1.id, u'geo', u'lon'))

        self.assertEqual(prop1.namespace, u'geo')
        self.assertEqual(prop2.namespace, u'geo')

        self.assertEqual(prop1.predicate, u'lat')
        self.assertEqual(prop2.predicate, u'lon')

        self.assertEqual(prop1.value, Decimal('12.96148'))
        self.assertEqual(prop2.value, Decimal('77.64431'))

    def test_property_cache(self):
        """The property cache should be transparent"""
        # Load the property cache by accessing it
        self.assertTrue("prop3" not in self.node1.properties)
        # Now add a property into the cache
        prop = Property(node=self.node1, name=u'proptest', value=u'testval')
        db.session.add(prop)
        db.session.commit()

        self.assertTrue(u'proptest' in self.node1._properties)
        self.assertTrue(u'proptest' in self.node1.properties)
        self.assertEqual(self.node1.properties[u'proptest'], u'testval')

        self.node1.properties['proptest'] = u'otherval'
        self.assertEqual(self.node1.properties[u'proptest'], u'otherval')
        self.assertEqual(self.node1._properties[u'proptest']._value, u'"otherval"')

    def test_property_invalid_value(self):
        """Setting an invalid value in the raw column doesn't break access"""
        prop = Property(node_id=self.node1.id, name=u'propval', _value=u'invalid_value')
        db.session.add(prop)
        db.session.commit()
        del prop

        # Confirm the property exists
        self.assertTrue(u'propval' in self.node1.properties)
        # Confirm the invalid value reads as None
        self.assertEqual(self.node1.properties[u'propval'], None)
        # Confirm the raw value hasn't been clobbered by a read operation
        self.assertEqual(self.node1._properties[u'propval']._value, u'invalid_value')
        # Set a new value
        self.node1.properties[u'propval'] = u'valid_value'
        # Confirm the new value has been set
        self.assertEqual(self.node1.properties[u'propval'], u'valid_value')

    def test_property_long_value(self):
        self.assertRaises(ValueError, self.node1.properties.__setitem__, 'test', 'a' * 1000)

    def test_inherited_properties(self):
        """getprop returns the value of a property from this or any parent node."""
        self.node2.properties[u'inherited_prop'] = u'inherited_val'
        # The property isn't available in the node's parent
        self.assertEqual(self.root.getprop(u'inherited_prop'), None)
        # The provided default value is returned
        self.assertEqual(self.root.getprop(u'inherited_prop', 1), 1)
        # The property is available in the node it was set on
        self.assertEqual(self.node2.getprop(u'inherited_prop'), u'inherited_val')
        # The property is not available in a sibling node
        self.assertEqual(self.node1.getprop(u'inherited_prop'), None)
        # The property is available from a child node any number of levels down
        self.assertEqual(self.node3.getprop(u'inherited_prop'), u'inherited_val')
        self.assertEqual(self.node4.getprop(u'inherited_prop'), u'inherited_val')


# --- Re-run tests with a different node type ---------------------------------

class TestTypeTree(TestNodeTree):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeTree, self).setUp()


class TestTypeDict(TestNodeDict):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeDict, self).setUp()

    def test_type(self):
        """
        Testing for the types of the nodes created in TestNodeDict.
        root & node2 will be of type 'node' because they do not use self.nodetype.
        """
        self.assertEqual(self.root.type, u'node')
        self.assertEqual(self.node1.type, u'test_type')
        self.assertEqual(self.node2.type, u'node')
        self.assertEqual(self.node3.type, u'test_type')
        self.assertEqual(self.node4.type, u'test_type')
        self.assertEqual(self.node5.type, u'test_type')


class TestTypeProperties(TestProperties):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeProperties, self).setUp()
