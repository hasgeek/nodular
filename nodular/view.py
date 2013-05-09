# -*- coding: utf-8 -*-

from functools import wraps
from werkzeug.routing import Map as UrlMap, Rule as UrlRule
from flask import g, abort

__all__ = ['NodeView']


class _NodeRoute(object):
    """Interim URL routing rule container for class initialization"""
    def __init__(self, rule, endpoint, f, methods, defaults):
        self.rule = rule
        self.endpoint = endpoint
        self.f = f
        self.methods = methods
        self.defaults = defaults
        # Pretend to be the wrapped function
        self.__name__ = f.__name__

    def __call__(self, *args, **kwargs):  # pragma: no cover
        """If we somehow got called instead of the wrapped function, pass the call."""
        return self.f(*args, **kwargs)


class NodeView(object):
    """
    Base class for node view handlers, to be initialized once per view render.
    Views are typically constructed like this::

        class MyNodeView(NodeView):
            @NodeView.route('/')
            def index(self):
                return u'index view'

            @NodeView.route('/edit', methods=['GET', 'POST'])
            @NodeView.route('/', methods=['PUT'])
            @NodeView.requires_permission('edit', 'siteadmin')
            def edit(self):
                return u'edit view'

            @NodeView.route('/delete', methods=['GET', 'POST'])
            @NodeView.route('/', methods=['DELETE'])
            @NodeView.requires_permission('delete', 'siteadmin')
            def delete(self):
                return u'delete view'

    :param node: Node that we are rendering a view for.
    :param user: User that the view is being rendered for.
    :type node: :class:`~nodular.node.Node`
    """
    class __metaclass__(type):
        """Metaclass for NodeView."""
        def __new__(cls, name, bases, attrs):
            # Add a url_map to the class
            url_map = UrlMap(strict_slashes=False)
            # Add a collection of (unbound) view functions
            view_functions = {}
            for base in bases:
                # Extend from url_map of base class
                if hasattr(base, 'url_map') and isinstance(base.url_map, UrlMap):
                    for rule in base.url_map.iter_rules():
                        url_map.add(rule.empty())
                # Extend from view_functions of base class
                if hasattr(base, 'view_functions') and isinstance(base.view_functions, dict):
                    view_functions.update(base.view_functions)
            for routeattr, route in attrs.items():
                if isinstance(route, _NodeRoute):
                    # For wrapped routes, add a rule for each layer of wrapping
                    endpoints = []
                    while isinstance(route, _NodeRoute):
                        # Save the endpoint name
                        endpoints.append(route.endpoint)
                        # Construct the url rule
                        url_rule = UrlRule(route.rule, endpoint=route.endpoint, methods=route.methods, defaults=route.defaults)
                        url_rule.provide_automatic_options = True
                        url_map.add(url_rule)
                        route = route.f
                    # Make a list of endpoints
                    for e in endpoints:
                        view_functions[e] = route
                    # Restore the original function
                    attrs[routeattr] = route
            # Finally, update the URL map and insert it into the class
            url_map.update()
            attrs['url_map'] = url_map
            attrs['view_functions'] = view_functions

            return type.__new__(cls, name, bases, attrs)

    def __init__(self, node, user=None, permissions=None):
        self.node = node
        self.user = user
        self.permissions = permissions

    @staticmethod
    def route(rule, endpoint=None, methods=None, defaults=None):
        """
        Decorator for view handlers.

        :param string rule: URL rule. See `Werkzeug routing`_ for syntax.
        :param string endpoint: Endpoint name, defaulting to method name.
        :param list methods: List of HTTP methods (default GET only).
        :param dict defaults: Default values to be passed to handler.

        .. _Werkzeug routing: http://werkzeug.pocoo.org/docs/routing/
        """
        def inner(f):
            # Get actual function when using stacked decorators
            realf = f
            while isinstance(realf, _NodeRoute):
                realf = realf.f
            local_endpoint = endpoint
            if local_endpoint is None:
                local_endpoint = realf.__name__
            local_methods = methods
            if local_methods is None:
                local_methods = ('GET',)
            local_methods = set(local_methods)
            local_methods.add('OPTIONS')
            return _NodeRoute(rule, local_endpoint, f, local_methods, defaults)
        return inner

    @staticmethod
    def requires_permission(permission, *other):
        """
        Decorator to enforce a permission requirement on a view.

        :param string permission: Permission required to access this handler.
        :param other: Other permissions, any of which can be used to access this handler.

        Available permissions are posted to ``flask.g.permissions`` for the lifetime of
        the request.
        """
        def inner(f):
            @wraps(f)
            def decorated_function(self, *args, **kwargs):
                has_permissions = self.node.permissions(self.user)
                if self.permissions is not None:
                    has_permissions.update(self.permissions)
                # Make permissions available for the lifetime of the request
                g.permissions = has_permissions
                if (permission in has_permissions) or (has_permissions & set(other)):
                    return f(self, *args, **kwargs)
                else:
                    abort(403)
            return decorated_function
        return inner
