# -*- coding: utf-8 -*-

"""
A node publisher translates between paths and URLs and publishes views for a given path.
Typical usage::

    from nodular import NodeRegistry, NodePublisher
    from myapp import app, root, registry

    assert isinstance(registry, NodeRegistry)
    # Publish everything under /
    publisher = NodePublisher(root, registry, u'/')

    @app.route('/<path:anypath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def publish_path(anypath):
        return publisher.publish(anypath)
"""

from urllib import urlencode
from urlparse import urljoin
from sqlalchemy.orm import subqueryload
from flask import request, redirect, g
from .node import pathjoin, Node, NodeAlias
from .exceptions import RootNotFound, NodeGone, ViewNotFound

__all__ = ['NodePublisher', 'TRAVERSE_STATUS']


class TRAVERSE_STATUS:
    """Traversal status codes."""
    #: Status code indicating an exact match for the path.
    MATCH = 0
    #: Status code indicating a :class:`~nodular.node.NodeAlias` redirect.
    REDIRECT = 1
    #: Status code indicating a partial path match.
    PARTIAL = 2
    #: Status code when nothing is found.
    NOROOT = 3
    #: Status code when a requested path is gone.
    GONE = 4


def _make_path_tree(basepath, path):
    """
    Return a list of paths leading to the destination path.

    :param basepath: Base path to search under. MUST begin with a '/'.
    :param path: Path to search for.
    :returns: Tuple of (full path, list of paths from root level to the given path)

    Tests::

        >>> _make_path_tree(u'/', u'')
        (u'/', [u'/'])
        >>> _make_path_tree(u'/', u'/')
        (u'/', [u'/'])
        >>> _make_path_tree(u'/', u'/foo')
        (u'/foo', [u'/', u'/foo'])
        >>> _make_path_tree(u'/', u'/foo/')
        (u'/foo', [u'/', u'/foo'])
        >>> _make_path_tree(u'/', u'foo')
        (u'/foo', [u'/', u'/foo'])
        >>> _make_path_tree(u'/', u'/foo/bar')
        (u'/foo/bar', [u'/', u'/foo', u'/foo/bar'])
        >>> _make_path_tree(u'/', u'foo/bar')
        (u'/foo/bar', [u'/', u'/foo', u'/foo/bar'])
        >>> _make_path_tree(u'/', u'/foo/bar/baz')
        (u'/foo/bar/baz', [u'/', u'/foo', u'/foo/bar', u'/foo/bar/baz'])
        >>> _make_path_tree(u'/foo', u'')
        (u'/foo', [u'/', u'/foo'])
        >>> _make_path_tree(u'/foo', u'/bar')
        (u'/foo/bar', [u'/', u'/foo', u'/foo/bar'])
        >>> _make_path_tree(u'/foo', u'/bar/')
        (u'/foo/bar', [u'/', u'/foo', u'/foo/bar'])
        >>> _make_path_tree(u'/foo', u'bar')
        (u'/foo/bar', [u'/', u'/foo', u'/foo/bar'])
    """
    if path.startswith(u'/'):
        path = path[1:]  # Strip leading slash
    if path.endswith(u'/'):
        path = path[:-1]  # Strip trailing slash
    if path == u'':
        searchpath = basepath
    else:
        searchpath = pathjoin(basepath, path)
    if searchpath == u'/':
        searchpaths = [u'/']
    else:
        parts = searchpath.split(u'/')
        searchpaths = [u'/'.join(parts[:x + 1]) for x in range(len(parts))]
        searchpaths[0] = u'/'
    return searchpath, searchpaths


class NodeDispatcher(object):
    """
    Dispatch a view. Internal class used by :meth:`NodePublisher.publish`.

    :param registry: Registry to look up views in.
    :param node: Node for which we are dispatching views.
    :param user: User for which we are rendering the view.
    :param permissions: Externally-granted permissions for this user.

    The view instance is made available as ``flask.g.view``.
    """
    def __init__(self, registry, node, user, permissions):
        self.registry = registry
        self.node = node
        self.user = user
        self.permissions = permissions

    def __call__(self, endpoint, args):
        if u'/' not in endpoint:  # pragma: no cover
            raise ViewNotFound(endpoint)  # We don't know about endpoints that aren't in 'view/function' syntax
        viewname, endpointname = endpoint.split(u'/', 1)
        view = self.registry.viewlist[viewname](self.node, self.user, self.permissions)
        g.view = view
        return view.view_functions[endpointname](view, **args)


class NodePublisher(object):
    """
    NodePublisher publishes node paths.

    :param root: Root node for lookups (Node instance or integer primary key id).
    :param registry: Registry for looking up views.
    :param string basepath: Base path to publish from, typically ``'/'``.
    :param string urlpath: URL path to publish to, typically also ``'/'``.
        Defaults to the :obj:`basepath` value.
    :type registry: :class:`~nodular.registry.NodeRegistry`

    NodePublisher may be instantiated either globally or per request, but requires a root node
    to query against. Depending on your setup, this may be available only at request time.
    """

    def __init__(self, root, registry, basepath, urlpath=None):
        self.root = root
        self.registry = registry
        if not basepath.startswith(u'/'):
            raise ValueError("Parameter ``basepath`` must be an absolute path starting with '/'")
        if basepath != u'/' and basepath.endswith(u'/'):
            basepath = basepath[:-1]  # Strip trailing slash for non-root paths
        self.basepath = basepath
        if urlpath is None:
            self.urlpath = basepath
        else:
            if not urlpath.startswith(u'/'):
                raise ValueError("Parameter ``urlpath`` must be an absolute path starting with '/'")
            self.urlpath = urlpath

    @property
    def root(self):
        if self.root_id is not None:
            return Node.query.get(self.root_id)

    @root.setter
    def root(self, value):
        if isinstance(value, Node):
            self.root_id = value.id
        else:
            self.root_id = value

    def traverse(self, path, redirect=True):
        """
        Traverse to the node at the given path, returning the closest matching node and status.

        :param path: Path to be traversed.
        :param redirect: If True (default), look for redirects when there's a partial match.
        :returns: Tuple of (status, node, path)

        Return value ``status`` is one of
        :attr:`~TRAVERSE_STATUS.MATCH`, :attr:`~TRAVERSE_STATUS.REDIRECT`,
        :attr:`~TRAVERSE_STATUS.PARTIAL`, :attr:`~TRAVERSE_STATUS.NOROOT` or
        :attr:`~TRAVERSE_STATUS.GONE`. For an exact :attr:`~TRAVERSE_STATUS.MATCH`,
        ``node`` is the found node and ``path`` is ``None``. For a
        :attr:`~TRAVERSE_STATUS.REDIRECT` or :attr:`~TRAVERSE_STATUS.PARTIAL` match, ``node``
        is the closest matching node and ``path`` is the URL path to redirect to OR the
        remaining unmatched path. :attr:`~TRAVERSE_STATUS.NOROOT` implies the root node is
        missing. If redirects are enabled and a :class:`~nodular.node.NodeAlias` is found
        indicating a node is deleted, status is :attr:`~TRAVERSE_STATUS.GONE`.

        :meth:`traverse` does not require a registry since it does not look up views.
        :class:`NodePublisher` may be initialized with ``registry=None`` if only used for
        traversal.
        """
        if not path.startswith(u'/'):
            path = u'/' + path
        if not path.startswith(self.urlpath):
            return TRAVERSE_STATUS.NOROOT, None, path
        path = path[len(self.urlpath):]

        nodepath, searchpaths = _make_path_tree(self.basepath, path)
        # Load nodes into the SQLAlchemy identity map so that node.parent does not
        # require a database roundtrip
        nodes = Node.query.filter(Node._root_id == self.root_id, Node.path.in_(searchpaths)).order_by('path').all()

        # Is there an exact matching node? Return it
        if len(nodes) > 0 and nodes[-1].path == nodepath:
            return TRAVERSE_STATUS.MATCH, nodes[-1], None

        # Is nothing found? Happens when there is no root node
        if len(nodes) == 0:
            return TRAVERSE_STATUS.NOROOT, None, None

        # Do we have a partial match? If redirects are enabled, check for a NodeAlias
        lastnode = nodes[-1]

        if len(lastnode.path) < len(self.basepath):
            # Our root node is missing. That's a NOROOT again
            return TRAVERSE_STATUS.NOROOT, None, None

        pathfragment = nodepath[len(lastnode.path):]
        redirectpath = None

        if pathfragment.startswith(u'/'):
            pathfragment = pathfragment[1:]

        status = TRAVERSE_STATUS.PARTIAL

        if redirect:
            aliasname = pathfragment.split(u'/', 1)[0]
            alias = NodeAlias.query.filter_by(parent=lastnode, name=aliasname).first()
            if alias is None:
                # No alias, but the remaining path may be handled by the node,
                # so return a partial match
                status = TRAVERSE_STATUS.PARTIAL
            elif alias.node is None:
                status = TRAVERSE_STATUS.GONE
            else:
                status = TRAVERSE_STATUS.REDIRECT
                if u'/' in pathfragment:
                    redirectpath = pathjoin(lastnode.path, alias.node.name, pathfragment.split(u'/', 1)[1])
                else:
                    redirectpath = pathjoin(lastnode.path, alias.node.name)
                redirectpath = redirectpath[len(self.basepath):]
                if redirectpath.startswith(u'/'):
                    redirectpath = pathjoin(self.urlpath, redirectpath[1:])
                else:
                    redirectpath = pathjoin(self.urlpath, redirectpath)
        else:
            # No redirects? Return partial match
            status = TRAVERSE_STATUS.PARTIAL

        # Add / prefix to pathfragment to help with URL matching
        # within the node
        pathfragment = u'/' + pathfragment

        if status == TRAVERSE_STATUS.REDIRECT:
            return status, lastnode, redirectpath
        elif status == TRAVERSE_STATUS.GONE:
            return status, lastnode, pathfragment
        else:
            return status, lastnode, pathfragment

    def publish(self, path, user=None, permissions=None):
        """
        Publish a path using views from the registry.

        :param path: Path to be published (relative to the initialized basepath).
        :param user: User we are rendering for (required for permission checks).
        :param permissions: Externally-granted permissions for this user.
        :returns: Result of the called view or :exc:`~werkzeug.exceptions.NotFound` exception if no view is found.

        :meth:`publish` uses :meth:`traverse` to find a node to publish.
        """
        status, node, pathfragment = self.traverse(path)
        if status == TRAVERSE_STATUS.REDIRECT:
            return redirect(pathfragment, code=302)  # Use 302 until we're sure we want to use 301
        elif status == TRAVERSE_STATUS.NOROOT:
            raise RootNotFound
        elif status == TRAVERSE_STATUS.GONE:
            raise NodeGone
        else:
            urls = self.registry.urlmaps[node.etype].bind_to_environ(request)
            if status == TRAVERSE_STATUS.MATCH:
                # Find '/' path handler. If none, return 404
                return urls.dispatch(NodeDispatcher(self.registry, node, user, permissions), path_info=u'/')
            elif status == TRAVERSE_STATUS.PARTIAL:
                return urls.dispatch(NodeDispatcher(self.registry, node, user, permissions), path_info=pathfragment)
            else:
                raise NotImplementedError("Unknown traversal status")  # pragma: no cover

    def url_for(self, node, action='view', _external=False, **kwargs):
        """
        Generates a URL to the given node with the view.

        :param node: Node instance
        :param endpoint: the endpoint of the URL (name of the function)
        """
        # TODO: Test that this is safe. What if the path is in between and not at the beginning?
        # Also: under what conditions is this '//' generated?
        def basepath2urlpath(x):
            return x.replace(self.basepath, self.urlpath, 1).replace('//', '/')

        node_urlmap = self.registry.urlmaps.get(node.etype)
        for rule in node_urlmap.iter_rules():
            viewname, endpointname = rule.endpoint.split('/', 1)
            if action == endpointname:
                path = node.path + rule.rule
                break
        else:
            raise ViewNotFound("Action '%s' does not exist for node type '%s'" % (action, node.etype))

        url = basepath2urlpath(path)

        if kwargs:
            url = '%s?%s' % (url, urlencode(kwargs))

        if _external:
            url = urljoin(request.host_url, url)
        return url
