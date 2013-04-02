# -*- coding: utf-8 -*-

import os.path
from .node import Node, NodeAlias

__all__ = ['TRAVERSE_STATUS', 'NodePublisher']


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
        searchpath = os.path.join(basepath, path)
    if searchpath == u'/':
        searchpaths = [u'/']
    else:
        parts = searchpath.split(u'/')
        searchpaths = [u'/'.join(parts[:x+1]) for x in range(len(parts))]
        searchpaths[0] = u'/'
    return searchpath, searchpaths


class NodePublisher(object):
    """
    NodePublisher publishes node trees.

    :param string basepath: Base path to publish from, typically ``'/'``.
    :param urlpath: URL path to publish to, typically also ``'/'``.
        Defaults to the :obj:`basepath` value.
    :type urlpath: string or None
    """

    def __init__(self, basepath, urlpath=None):
        if not basepath.startswith(u'/'):
            raise ValueError("Parameter ``basepath`` must be an absolute path starting with '/'.")
        if basepath != u'/' and basepath.endswith(u'/'):
            basepath = basepath[:-1]  # Strip trailing slash for non-root paths
        self.basepath = basepath
        if urlpath is None:
            self.urlpath = basepath
        else:
            if not urlpath.startswith(u'/'):
                raise ValueError("Parameter ``urlpath`` must be an absolute path starting with '/'.")
            self.urlpath = urlpath

    def traverse(self, path, redirect=True):
        """
        Traverse to the node at the given path, returning the closest matching node and status.

        :param path: Path to be traversed.
        :param redirect: If True (default), look for redirects when there's a partial match.
        :returns: Tuple of (status, node, path) where status is one of
            :attr:`~TRAVERSE_STATUS.MATCH`, :attr:`~TRAVERSE_STATUS.REDIRECT`,
            :attr:`~TRAVERSE_STATUS.PARTIAL`, :attr:`~TRAVERSE_STATUS.NOROOT` or
            :attr:`~TRAVERSE_STATUS.GONE`. For an exact :attr:`~TRAVERSE_STATUS.MATCH`,
            ``node`` is the found node and ``path`` is ``None``. For a
            :attr:`~TRAVERSE_STATUS.REDIRECT` or :attr:`~TRAVERSE_STATUS.PARTIAL` match, ``node``
            is the closest matching node and ``path`` is the path to redirect to OR the the
            remaining unmatched path. If the root node is missing, status
            :attr:`~TRAVERSE_STATUS.NOROOT` is returned. If redirects are enabled and a
            :class:`~nodular.node.NodeAlias` is found indicating a node is deleted, status
            :attr:`~TRAVERSE_STATUS.GONE` is returned.
        """
        nodepath, searchpaths = _make_path_tree(self.basepath, path)
        # Load nodes into the SQLAlchemy identity map so that node.parent does not
        # require a database roundtrip
        nodes = Node.query.filter(Node.path.in_(searchpaths)).order_by('path').all()

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
                # No alias, but the remaining path may be handled specially by the node,
                # so return a partial match
                status = TRAVERSE_STATUS.PARTIAL
            elif alias.node is None:
                status = TRAVERSE_STATUS.GONE
            else:
                status = TRAVERSE_STATUS.REDIRECT
                if u'/' in pathfragment:
                    redirectpath = os.path.join(lastnode.path, alias.node.name, pathfragment.split(u'/', 1)[1])
                else:
                    redirectpath = os.path.join(lastnode.path, alias.node.name)
                redirectpath = redirectpath[len(self.basepath):]
                if redirectpath.startswith(u'/'):
                    redirectpath = os.path.join(self.urlpath, redirectpath[1:])
                else:
                    redirectpath = os.path.join(self.urlpath, redirectpath)
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
