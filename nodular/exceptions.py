# -*- coding: utf-8 -*-

"""
Exceptions raised by Nodular.
"""

from werkzeug.exceptions import NotFound, Gone

__all__ = ['NodeNotFound', 'RootNotFound', 'NodeGone', 'ViewNotFound']


class NodeNotFound(NotFound):
    pass


class RootNotFound(NodeNotFound):
    pass


class NodeGone(Gone):
    pass


class ViewNotFound(NotFound):
    pass
