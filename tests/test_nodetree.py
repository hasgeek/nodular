# -*- coding: utf-8 -*-

import unittest
from sqlalchemy.exc import IntegrityError
from nodular import Node
from .test_db import db, TestDatabaseFixture


class TestNodeTree(TestDatabaseFixture):
    def test_makenode(self):
        node = Node(name=u'node', title=u'Node', user=self.user1)
        db.session.add(node)
        db.session.commit()

    def test_root_node_name_no_conflict(self):
        node1 = Node(name=u'node', title=u'Node 1', user=self.user1)
        node2 = Node(name=u'node', title=u'Node 2', user=self.user1)
        db.session.add(node1)
        db.session.add(node2)
        db.session.commit()
        # This test passes because the presence of a null parent_id
        # inhibits the unique constraint on ('name', 'parent_id')

    def test_parented_node_name_conflict(self):
        root = Node(name=u'node', title=u'Root Node', user=self.user1)
        node1 = Node(name=u'node', title=u'Node 1', user=self.user1, parent=root)
        node2 = Node(name=u'node', title=u'Node 2', user=self.user1, parent=root)
        db.session.add(root)
        db.session.add(node1)
        db.session.add(node2)
        self.assertRaises(IntegrityError, db.session.commit)


if __name__ == '__main__':
    unittest.main()
