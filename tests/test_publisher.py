# -*- coding: utf-8 -*-

import unittest
from nodular import Node, NodePublisher
from .test_db import db, TestDatabaseFixture
from .test_nodetree import TestType


class TestNodeTraversal(TestDatabaseFixture):
    """Dictionary access to node hierarchy."""
    def setUp(self):
        super(TestNodeTraversal, self).setUp()
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

    def test_invalid_publisher(self):
        """Publisher paths must be absolute."""
        self.assertRaises(ValueError, NodePublisher, u'node2')
        self.assertRaises(ValueError, NodePublisher, u'/node2', u'node2')

    def test_traverse_basepaths(self):
        """Publisher basepaths must be stored accurately."""
        self.assertEqual(self.rootpub.basepath, u'/')
        self.assertEqual(self.nodepub.basepath, u'/node2')

        newpub = NodePublisher(u'/node2/')
        self.assertEqual(newpub.basepath, '/node2')

    def test_traverse_noroot_root(self):
        """If there's no root node, status is NOROOT (root publisher)."""
        db.session.delete(self.root)
        db.session.commit()
        status, node, path = self.rootpub.traverse(u'/node2')
        self.assertEqual(status, self.rootpub.NOROOT)

    def test_traverse_noroot_node(self):
        """If there's no root node, status is NOROOT (node publisher)."""
        db.session.delete(self.node2)
        db.session.commit()
        status, node, path = self.nodepub.traverse(u'/')
        self.assertEqual(status, self.nodepub.NOROOT)

    def test_traverse_match_root(self):
        """Traversal direct match for root publisher."""
        status, node, path = self.rootpub.traverse(u'/node2')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, None)

        status, node, path = self.rootpub.traverse(u'/node2/node3')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, None)

        status, node, path = self.rootpub.traverse(u'/node2/node3/node4')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node4)
        self.assertEqual(path, None)

    def test_traverse_match_root_slashless(self):
        """Traversal direct match for root publisher (without leading slashes)."""
        status, node, path = self.rootpub.traverse(u'node2')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, None)

        status, node, path = self.rootpub.traverse(u'node2/node3')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, None)

        status, node, path = self.rootpub.traverse(u'node2/node3/node4')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node4)
        self.assertEqual(path, None)

    def test_traverse_match_node(self):
        """Traversal direct match for node publisher."""
        status, node, path = self.nodepub.traverse(u'/')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, None)

        status, node, path = self.nodepub.traverse(u'/node3')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, None)

        status, node, path = self.nodepub.traverse(u'/node3/node4')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node4)
        self.assertEqual(path, None)

    def test_traverse_match_node_slashless(self):
        """Traversal direct match for node publisher (without leading slashes)."""
        status, node, path = self.nodepub.traverse(u'')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, None)

        status, node, path = self.nodepub.traverse(u'node3')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, None)

        status, node, path = self.nodepub.traverse(u'node3/node4')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node4)
        self.assertEqual(path, None)

    def test_traverse_partial_match(self):
        """Test for partial path matching."""
        status, node, path = self.rootpub.traverse(u'/nodeX')
        self.assertEqual(status, self.rootpub.PARTIAL)
        self.assertEqual(node, self.root)
        self.assertEqual(path, 'nodeX')

        status, node, path = self.rootpub.traverse(u'/node3/node4')
        self.assertEqual(status, self.rootpub.PARTIAL)
        self.assertEqual(node, self.root)
        self.assertEqual(path, 'node3/node4')

        status, node, path = self.rootpub.traverse(u'/node2/node4')
        self.assertEqual(status, self.rootpub.PARTIAL)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, 'node4')

    def test_traverse_redirect_root(self):
        """Renamed nodes result in REDIRECT status (root publisher)."""
        self.node2.name = u'nodeX'
        db.session.commit()

        status, node, path = self.rootpub.traverse(u'/nodeX')
        self.assertEqual(status, self.rootpub.MATCH)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, None)

        status, node, path = self.rootpub.traverse(u'/node2')
        self.assertEqual(status, self.rootpub.REDIRECT)
        self.assertEqual(node, self.root)
        self.assertEqual(path, '/nodeX')

        status, node, path = self.rootpub.traverse(u'/node2/node3')
        self.assertEqual(status, self.rootpub.REDIRECT)
        self.assertEqual(node, self.root)
        self.assertEqual(path, '/nodeX/node3')

        status, node, path = self.rootpub.traverse(u'/node2/node4')
        self.assertEqual(status, self.rootpub.REDIRECT)
        self.assertEqual(node, self.root)
        self.assertEqual(path, '/nodeX/node4')

    def test_traverse_redirect_node(self):
        """Renamed nodes result in REDIRECT status (node publisher)."""
        self.node3.name = u'nodeX'
        db.session.commit()

        status, node, path = self.nodepub.traverse(u'/nodeX')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, None)

        status, node, path = self.nodepub.traverse(u'/node3')
        self.assertEqual(status, self.nodepub.REDIRECT)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, '/nodeX')

        status, node, path = self.nodepub.traverse(u'/node3/node4')
        self.assertEqual(status, self.nodepub.REDIRECT)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, '/nodeX/node4')

    def test_traverse_redirect_subnode(self):
        """Renamed nodes result in REDIRECT status (node publisher)."""
        self.node4.name = u'nodeX'
        db.session.commit()

        status, node, path = self.nodepub.traverse(u'/node3/nodeX')
        self.assertEqual(status, self.nodepub.MATCH)
        self.assertEqual(node, self.node4)
        self.assertEqual(path, None)

        status, node, path = self.nodepub.traverse(u'/node3/node4')
        self.assertEqual(status, self.nodepub.REDIRECT)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, '/node3/nodeX')

        self.nodepub.urlpath = self.nodepub.basepath

        status, node, path = self.nodepub.traverse(u'/node3/node4')
        self.assertEqual(status, self.nodepub.REDIRECT)
        self.assertEqual(node, self.node3)
        self.assertEqual(path, '/node2/node3/nodeX')

    def test_traverse_gone_root(self):
        """Deleted nodes cause a GONE response status (root publisher)."""
        db.session.delete(self.node3)
        db.session.commit()

        status, node, path = self.rootpub.traverse(u'/node2/node3')
        self.assertEqual(status, self.rootpub.GONE)
        self.assertEqual(node, self.node2)

        status, node, path = self.rootpub.traverse(u'/node2/node3/node4')
        self.assertEqual(status, self.rootpub.GONE)
        self.assertEqual(node, self.node2)

    def test_traverse_gone_node(self):
        """Deleted nodes cause a GONE response status (node publisher)."""
        db.session.delete(self.node3)
        db.session.commit()

        status, node, path = self.nodepub.traverse(u'/node3')
        self.assertEqual(status, self.nodepub.GONE)
        self.assertEqual(node, self.node2)

        status, node, path = self.nodepub.traverse(u'/node3/node4')
        self.assertEqual(status, self.nodepub.GONE)
        self.assertEqual(node, self.node2)

    def test_traverse_gone_root_noredirect(self):
        """Deleted nodes return PARTIAL when redirects are disabled (root publisher)."""
        db.session.delete(self.node3)
        db.session.commit()

        status, node, path = self.rootpub.traverse(u'/node2/node3', redirect=False)
        self.assertEqual(status, self.rootpub.PARTIAL)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, u'node3')

        status, node, path = self.rootpub.traverse(u'/node2/node3/node4', redirect=False)
        self.assertEqual(status, self.rootpub.PARTIAL)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, u'node3/node4')

    def test_traverse_gone_node_noredirect(self):
        """Deleted nodes return PARTIAL when redirects are disabled (node publisher)."""
        db.session.delete(self.node3)
        db.session.commit()

        status, node, path = self.nodepub.traverse(u'/node3', redirect=False)
        self.assertEqual(status, self.nodepub.PARTIAL)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, u'node3')

        status, node, path = self.nodepub.traverse(u'/node3/node4', redirect=False)
        self.assertEqual(status, self.nodepub.PARTIAL)
        self.assertEqual(node, self.node2)
        self.assertEqual(path, u'node3/node4')


class TestTypeTraversal(TestNodeTraversal):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeTraversal, self).setUp()


if __name__ == '__main__':
    unittest.main()
