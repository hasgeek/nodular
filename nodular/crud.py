# -*- coding: utf-8 -*-

from functools import wraps
from werkzeug.routing import Map as UrlMap, Rule as UrlRule
from flask import request

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

    def __call__(self, *args, **kwargs):
        """If we somehow got called instead of the wrapped function, pass the call."""
        return self.f(*args, **kwargs)


class _InitNodeView(type):
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
        for route in attrs:
            if isinstance(route, _NodeRoute):
                # Construct the url rule
                url_rule = UrlRule(route.rule, endpoint=route.endpoint, methods=route.methods, defaults=route.defaults)
                url_rule.provide_automatic_options = True
                url_map.add(url_rule)
                view_functions[route.endpoint] = route.f
                attrs[route] = route.f  # Restore the original function
        # Finally, update the URL map and insert it into the class
        url_map.update()
        attrs['url_map'] = url_map
        attrs['view_functions'] = view_functions

        return super(_InitNodeView, cls).__new__(cls, name, bases, attrs)


class NodeView(object):
    """
    Base class for node view handlers, to be initialized once per view render.

    :param node: Node that we are rendering a view for.
    :type node: :class:`~nodular.node.Node` or None. If None, implies a new node.
    """
    __metaclass__ = _InitNodeView

    def __init__(self, node=None):
        self.node = node
        self.urls = self.url_map.bind_to_environ(request)

    @staticmethod
    def route(rule, endpoint=None, methods=None, defaults=None):
        @wraps
        def inner(f):
            local_endpoint = endpoint
            if local_endpoint is None:
                local_endpoint = f.__name__
            local_methods = methods
            if local_methods is None:
                local_methods = ('GET',)
            local_methods = set(local_methods)
            local_methods.add('OPTIONS')
            return _NodeRoute(rule, local_endpoint, f, local_methods, defaults)
        return inner
