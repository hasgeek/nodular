# -*- coding: utf-8 -*-

from functools import wraps
from werkzeug.routing import Map as UrlMap, Rule as UrlRule
from flask import g, abort, render_template, request, current_app
from coaster.views import jsonp

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
                    # Construct the url rule
                    url_rule = UrlRule(route.rule, endpoint=route.endpoint, methods=route.methods, defaults=route.defaults)
                    url_rule.provide_automatic_options = True
                    url_map.add(url_rule)
                    view_functions[route.endpoint] = route.f
                    attrs[routeattr] = route.f  # Restore the original function
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
            while isinstance(f, _NodeRoute):
                f = f.f
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

    @staticmethod
    def render_with(template):
        """
        Decorator to render the wrapped function with the given template (or dictionary
        of mimetype keys to templates, where the template is a string name of a template
        or a callable). The function's return value must be a dictionary. Usage::

            class MyNodeView(NodeView):
                @NodeView.route('/myview')
                @NodeView.render_with('myview.html')
                def myview(self):
                    return {'data': 'value'}

                @NodeView.route('/otherview')
                @NodeView.render_with({
                    'text/html': 'otherview.html',
                    'text/xml': 'otherview.xml'})
                def otherview(self):
                    return {'data': 'value'}

        When a mimetype is specified and the template is not a callable, the response is
        returned with the same mimetype. Callable templates must return Response objects
        to ensure the correct mimetype is set.
        """
        templates = {
            'application/json': jsonp,
            'text/json': jsonp,
            'text/x-json': jsonp,
            }
        if isinstance(template, (basestring, tuple, list)):
            templates['*/*'] = template
        elif isinstance(template, dict):
            templates.update(template)
        else:
            raise ValueError("Expected string or dict for template")

        def inner(f):
            @wraps(f)
            def decorated_function(self, *args, **kwargs):
                render = kwargs.pop('_render', True)
                result = f(self, *args, **kwargs)
                use_mimetype = None
                if render:
                    try:
                        mimetypes = [m.strip() for m in request.headers.get(
                            'Accept', '').replace(';', ',').split(',') if '/' in m]
                        use_mimetype = None
                        for mimetype in mimetypes:
                            if mimetype in templates:
                                use_mimetype = mimetype
                                break
                        if use_mimetype is None:
                            if '*/*' in templates:
                                use_mimetype = '*/*'
                    except RuntimeError:  # Not in a request context
                        pass
                # Now render the result with the template for the mimetype
                if use_mimetype is not None:
                    if callable(templates[use_mimetype]):
                        rendered = templates[use_mimetype](result)
                    else:
                        if use_mimetype != '*/*':
                            rendered = current_app.response_class(
                                render_template(templates[use_mimetype], **result),
                                mimetype=use_mimetype)
                        else:
                            rendered = render_template(templates[use_mimetype], **result)
                    return rendered
                else:
                    return result
            return decorated_function
        return inner
