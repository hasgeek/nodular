# -*- coding: utf-8 -*-

"""
The node registry is a place to list the relationships between node types
and their views.

Nodular does *not* provide a global instance of :class:`NodeRegistry`. Since
the registry determines what is available in an app, registries should be
constructed as app-level globals.
"""

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from collections import defaultdict
from werkzeug.routing import Map as UrlMap

__all__ = ['NodeRegistry']


def dottedname(entity):
    """Return a dotted name to the given named entity"""
    return entity.__module__ + '.' + entity.__name__


class RegistryItem(object):
    """Container for registry entry data"""
    pass


class NodeRegistry(object):
    """
    Registry for node types and node views.
    """
    def __init__(self):
        self.nodes = OrderedDict()
        self.child_nodetypes = defaultdict(set)
        self.nodeviews = defaultdict(list)
        self.viewlist = {}
        self.urlmaps = defaultdict(lambda: UrlMap(strict_slashes=False))

    def register_node(self, model, view=None,
            child_nodetypes=None, parent_nodetypes=None):
        """
        Register a node.

        :param model: Node model.
        :param view: View for this node type (optional).
        :param list child_nodetypes: Allowed child nodetypes.
            None or empty implies no children allowed.
        :param list parent_nodetypes: Nodetypes that this node can be a child of.
        :type model: :class:`~nodular.node.Node`
        :type view: :class:`~nodular.crud.NodeView`

        The special value ``'*'`` in ``child_nodetypes`` implies that this node
        is a generic container. ``'*'`` in ``parent_nodetypes`` implies that
        this node can appear in any container that has ``'*'`` in
        ``child_nodetypes``.
        """

        item = RegistryItem()
        item.model = model
        item.nodetype = model.__type__
        item.title = model.__title__
        self.nodes[item.nodetype] = item

        if view is not None:
            self.register_view(item.nodetype, view)

        if child_nodetypes is not None:
            self.child_nodetypes[item.nodetype].update(child_nodetypes)
        for ptype in parent_nodetypes or []:
            self.child_nodetypes[ptype].add(item.nodetype)

    def register_view(self, nodetype, view):
        """
        Register a view.

        :param string nodetype: Node type that this view renders for.
        :param view: View class.
        :type view: :class:`~nodular.view.NodeView`
        """
        self.nodeviews[nodetype].append(view)
        dotted_view_name = dottedname(view)
        self.viewlist[dotted_view_name] = view
        # Combine URL rules from across views for the same nodetype
        for rule in view.url_map.iter_rules():
            rule = rule.empty()
            rule.endpoint = dotted_view_name + '/' + rule.endpoint
            self.urlmaps[nodetype].add(rule)
        self.urlmaps[nodetype].update()
