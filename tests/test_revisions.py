# -*- coding: utf-8 -*-

import unittest
from nodular import Node, RevisionedNodeMixin
from .test_db import db, TestDatabaseFixture


class MyDocument(RevisionedNodeMixin, Node):
    __tablename__ = u'my_document'


class MyDocumentRevision(MyDocument.RevisionMixin, db.Model):
    content = db.Column(db.UnicodeText, nullable=False, default=u'')


class YourDocument(RevisionedNodeMixin, Node):
    __tablename__ = u'your_document'


class YourDocumentRevision(YourDocument.RevisionMixin, db.Model):
    content = db.Column(db.UnicodeText, nullable=False, default=u'')


class TestNodeRevisions(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeRevisions, self).setUp()
        self.root = Node(name=u'root', title=u'Root Node')
        db.session.add(self.root)

    def test_revision_class_attributes(self):
        from sqlalchemy.orm.attributes import InstrumentedAttribute
        self.assertEqual(MyDocumentRevision.__parent_model__, MyDocument)
        self.assertEqual(MyDocument.__revision_model__, MyDocumentRevision)
        self.assertEqual(MyDocumentRevision.__tablename__, MyDocument.__tablename__ + '_revisions')
        self.assertTrue(isinstance(MyDocumentRevision.created_at, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.updated_at, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.node_id, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.node, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.language, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.status, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.user_id, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.user, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.previous_id, InstrumentedAttribute))
        self.assertTrue(isinstance(MyDocumentRevision.previous, InstrumentedAttribute))

        self.assertEqual(YourDocumentRevision.__parent_model__, YourDocument)
        self.assertEqual(YourDocument.__revision_model__, YourDocumentRevision)
        self.assertEqual(YourDocumentRevision.__tablename__, YourDocument.__tablename__ + '_revisions')
        self.assertTrue(isinstance(YourDocumentRevision.created_at, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.updated_at, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.node_id, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.node, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.language, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.status, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.user_id, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.user, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.previous_id, InstrumentedAttribute))
        self.assertTrue(isinstance(YourDocumentRevision.previous, InstrumentedAttribute))

    def test_default_revision(self):
        doc1 = MyDocument(name=u'doc', title=u'Document', parent=self.root)
        db.session.add(doc1)
        db.session.commit()
        # The node is a stub initially with no content
        self.assertEqual(len(list(doc1.revisions)), 0)
        revision = doc1.revise()
        self.assertEqual(revision.id, None)
        db.session.commit()
        self.assertNotEqual(revision.id, None)


if __name__ == '__main__':
    unittest.main()