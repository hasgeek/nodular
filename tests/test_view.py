# -*- coding: utf-8 -*-

import unittest
from werkzeug.exceptions import NotFound, Forbidden
from flask import Response
from jinja2 import TemplateNotFound
from coaster.views import jsonp
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


class RenderedView(NodeView):
    @NodeView.route('/renderedview1')
    @NodeView.render_with('renderedview1.html')
    def myview(self):
        return {'data': 'value'}

    @NodeView.route('/renderedview2')
    @NodeView.render_with({
        'text/html': 'renderedview2.html',
        'text/xml': 'renderedview2.xml',
        'text/plain': viewcallable})
    def otherview(self):
        return {'data': 'value'}

# --- Tests -------------------------------------------------------------------


class TestNodeView(unittest.TestCase):
    def test_view_route(self):
        """Test that NodeView.route defines a route."""
        self.assertTrue(hasattr(MyNodeView, 'url_map'))
        self.assertEqual(type(MyNodeView.index), type(MyNodeView.dummy))
        self.assertEqual(len(list(MyNodeView.url_map.iter_rules())), 1)


class TestNodeViews(TestDatabaseFixture):
    def setUp(self):
        super(TestNodeViews, self).setUp()

        self.registry = NodeRegistry()
        self.registry.register_node(Node, view=MyNodeView, child_nodetypes=['*'])
        self.registry.register_node(TestType, view=MyNodeView, child_nodetypes=['*'], parent_nodetypes=['*'])

        self.registry.register_view('node', ExpandedNodeView)
        self.registry.register_view('test_type', ExpandedNodeView)

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

        self.rootpub = NodePublisher(self.registry, u'/')
        self.nodepub = NodePublisher(self.registry, u'/node2', u'/')

    def test_publishview(self):
        """Publish a default view."""
        with self.app.test_request_context():
            response = self.rootpub.publish(u'/node2')
        self.assertEqual(response, 'node-index')

    def test_methods(self):
        """Publish views with different methods."""
        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertEqual(response, 'edit-GET')

        with self.app.test_request_context(method='POST'):
            response = self.rootpub.publish(u'/node2/edit')
        self.assertEqual(response, 'edit-POST')

        with self.app.test_request_context(method='GET'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-GET')

        with self.app.test_request_context(method='POST'):
            response = self.rootpub.publish(u'/node2/multimethod')
        self.assertEqual(response, 'multimethod-POST')

        with self.app.test_request_context(method='GET'):
            self.assertRaises(NotFound, self.rootpub.publish, u'/node2/random')


class TestTypeViews(TestNodeViews):
    def setUp(self):
        self.nodetype = TestType
        super(TestTypeViews, self).setUp()


class TestPermissionAndRenderedViews(TestDatabaseFixture):
    def setUp(self):
        super(TestPermissionAndRenderedViews, self).setUp()

        self.registry = NodeRegistry()
        self.registry.register_node(TestType, view=RestrictedView)
        self.registry.register_view('test_type', RenderedView)
        self.root = Node(name=u'root', title=u'Root Node')
        self.node = TestType(name=u'node', title=u'Node', parent=self.root)
        db.session.add_all([self.root, self.node])
        db.session.commit()
        self.publisher = NodePublisher(self.registry, u'/')

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
            self.assertRaises(Forbidden, self.publisher.publish, u'/node/admin')

    def test_render(self):
        """
        Test rendered views.
        """
        # For this test to pass, the render_view decorator must call render_template
        # with the correct template name. Since the templates don't actually exist,
        # we'll get a TemplateNotFound exception, so our "test" is to confirm that the
        # missing template is the one that was supposed to be rendered.
        with self.app.test_request_context(method='GET', headers=[('Accept', '')]):
            try:
                self.publisher.publish(u'/node/renderedview1')
            except TemplateNotFound, e:
                self.assertEqual(str(e), 'renderedview1.html')
            else:
                raise Exception("Wrong template rendered")

        for acceptheader, template in [
                ('text/html,text/xml,*/*', 'renderedview2.html'),
                ('text/xml,text/html,*/*', 'renderedview2.xml')]:
            with self.app.test_request_context(method='GET', headers=[('Accept', acceptheader)]):
                try:
                    self.publisher.publish(u'/node/renderedview2')
                except TemplateNotFound, e:
                    self.assertEqual(str(e), template)
                else:
                    raise Exception("Wrong template rendered")

        # The application/json and text/plain renderers do exist, so we should get
        # a valid return value from them.
        with self.app.test_request_context(method='GET', headers=[('Accept', 'application/json')]):
            response = self.publisher.publish(u'/node/renderedview2')
            self.assertTrue(isinstance(response, Response))
            self.assertEqual(response.data, jsonp({"data": "value"}).data)
        with self.app.test_request_context(method='GET', headers=[('Accept', 'text/plain')]):
            response = self.publisher.publish(u'/node/renderedview2')
            self.assertTrue(isinstance(response, Response))
            self.assertEqual(response.data, "{'data': 'value'}")
