# -*- coding: utf-8 -*-

import unittest
from werkzeug.exceptions import NotFound, Forbidden, Gone
from flask import Response
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
    @NodeView.route('/', methods=['GET', 'POST'])
    def index(self):
        # This never gets called for GET because MyNodeView.index is registered first
        return u'expanded-index'

    @NodeView.route('/edit', methods=['GET'])
    def editget(self):
        return u'edit-GET'

    @NodeView.route('/edit', methods=['POST'])
    def editpost(self):
        return u'edit-POST'

    @NodeView.route('/multimethod', methods=['GET', 'POST'])
    @NodeView.route('/multimethod', methods=['PUT'])
    def multimethod(self):
        from flask import request
        return u'multimethod-' + request.method


class RestrictedView(MyNodeView):
    @NodeView.route('/view')
    @NodeView.requires_permission('view')
    def view(self):
        return u'view'

    @NodeView.route('/admin')
    @NodeView.requires_permission('admin')
    def admin(self):
        return u'admin'


def viewcallable(data):
    return Response(repr(data), mimetype='text/plain')


# --- Tests -------------------------------------------------------------------


class TestNodeView(unittest.TestCase):
    def test_view_route(self):
        """Test that NodeView.route defines a route."""
        self.assertTrue(hasattr(MyNodeView, 'url_map'))
        self.assertEqual(type(MyNodeView.index), type(MyNodeView.dummy))
        self.assertEqual(len(list(MyNodeView.url_map.iter_rules())), 1)


class TestPublishViews(TestDatabaseFixture):
    def setUp(self):
        super(TestPublishViews, self).setUp()

        self.registry = NodeRegistry()
        self.registry.register_node(Node, view=MyNodeView, child_nodetypes=['*'])
        self.registry.register_node(TestType, view=MyNodeView, child_nodetypes=['*'], parent_nodetypes=['*'])

        self.registry.register_view('node', ExpandedNodeView)
        self.registry.register_view(TestType, ExpandedNodeView)

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

        self.rootpub = NodePublisher(self.root, self.registry, u'/')
        self.nodepub = NodePublisher(self.root, self.registry, u'/node2', u'/')
        self.nodepub_defaulturl = NodePublisher(self.root, self.registry, u'/node2')

    def test_init_root(self):
        deferpub = NodePublisher(None, self.registry, u'/')
        self.assertEqual(deferpub.root, None)
        deferpub.init_root(self.node1)
        self.assertEqual(deferpub.root, self.node1)

    def test_publishview(self):
        """Publish a default view."""
        with self.app.test_request_context():
            response = self.rootpub.publish(u'/node2')
        self.assertEqual(response, 'node-index')
        with self.app.test_request_context():
            response = self.nodepub.publish(u'/')
        self.assertEqual(response, 'node-index')
        with self.app.test_request_context():
            response = self.nodepub_defaulturl.publish(u'/node2')
        self.assertEqual(response, 'node-index')

    def test_methods(self):
        """Publish views with different methods."""
        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertEqual(response, 'edit-GET')

        with self.app.test_request_context(method='GET'):
            response = self.nodepub.publish(u'/edit')
        self.assertEqual(response, 'edit-GET')

        with self.app.test_request_context(method='POST'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertEqual(response, 'edit-POST')

        with self.app.test_request_context(method='POST'):
            response = self.nodepub.publish(u'/edit')
        self.assertEqual(response, 'edit-POST')

        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-GET')

        with self.app.test_request_context(method='GET'):
            response = self.nodepub.publish(u'/multimethod')
        self.assertEqual(response, 'multimethod-GET')

        with self.app.test_request_context(method='POST'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-POST')

        with self.app.test_request_context(method='POST'):
            response = self.nodepub.publish(u'/multimethod')
        self.assertEqual(response, 'multimethod-POST')

        with self.app.test_request_context(method='PUT'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-PUT')

        with self.app.test_request_context(method='PUT'):
            response = self.nodepub.publish(u'/multimethod')
        self.assertEqual(response, 'multimethod-PUT')

        with self.app.test_request_context(method='GET'):
            self.assertRaises(NotFound, self.rootpub.publish, u'/node2/random')

        with self.app.test_request_context(method='GET'):
            self.assertRaises(NotFound, self.nodepub.publish, u'/random')

    def test_redirect_gone(self):
        """
        Test the publisher's 30x and 410 responses.
        """
        self.node2.name = u'nodeX'
        db.session.commit()
        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertTrue(response.status[:3] in ['301', '302'])
        self.assertEqual(response.headers['Location'], '/nodeX/edit')

        db.session.delete(self.node2)
        db.session.commit()
        with self.app.test_request_context(method='GET'):
            self.assertRaises(Gone, self.rootpub.publish, u'/node2/edit')

    def test_noroot(self):
        """
        Test the publisher's NOROOT 404 response.
        """
        newpub = NodePublisher(self.root, self.registry, u'/no-node')
        with self.app.test_request_context(method='GET'):
            self.assertRaises(NotFound, newpub.publish, '/')


class TestTypeViews(TestPublishViews):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeViews, self).setUp()


class TestPermissionViews(TestDatabaseFixture):
    def setUp(self):
        super(TestPermissionViews, self).setUp()

        self.registry = NodeRegistry()
        self.registry.register_node(TestType, view=RestrictedView)
        self.root = Node(name=u'root', title=u'Root Node')
        self.node = TestType(name=u'node', title=u'Node', parent=self.root)
        db.session.add_all([self.root, self.node])
        db.session.commit()
        self.publisher = NodePublisher(self.root, self.registry, u'/')

    def test_view(self):
        """
        Test access to the restricted view.
        """
        # No permission required to access '/'
        with self.app.test_request_context(method='GET'):
            response = self.publisher.publish(u'/node')
        self.assertEqual(response, u'node-index')
        # 'view' permission is granted to everyone on TestType
        with self.app.test_request_context(method='GET'):
            response = self.publisher.publish(u'/node/view')
        self.assertEqual(response, u'view')
        # 'admin' permission is granted to no one on TestType
        with self.app.test_request_context(method='GET'):
            self.assertRaises(Forbidden, self.publisher.publish, u'/node/admin',
                user=self.user1, permissions=['siteadmin'])
