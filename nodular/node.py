# -*- coding: utf-8 -*-

"""
Nodular's NodeMixin and Node models are the base classes for all content
objects.
"""

import weakref
from collections import MutableMapping
from werkzeug import cached_property

from sqlalchemy import Column, String, Unicode, DateTime
from sqlalchemy import ForeignKey, UniqueConstraint, Index
from sqlalchemy import event
from sqlalchemy.orm import validates, mapper, relationship, backref
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from coaster import newid
from coaster.sqlalchemy import TimestampMixin, PermissionMixin, BaseScopedNameMixin, JsonDict

from .db import db

__all__ = ['Node', 'NodeAlias', 'NodeMixin', 'ProxyDict', 'pathjoin']

_marker = []


def pathjoin(a, *p):
    """
    Join two or more pathname components, inserting '/' as needed.
    If any component is an absolute path, all previous path components
    will be discarded.

    .. note:: This function is the same as :func:`os.path.join` on
        POSIX systems but is reproduced here so that Nodular can be used
        in non-POSIX environments.
    """
    path = a
    for b in p:  # pragma: no cover
        if b.startswith(u'/'):
            path = b
        elif path == u'' or path.endswith(u'/'):
            path += b
        else:
            path += u'/' + b
    return path


# Adapted from
# https://bitbucket.org/sqlalchemy/sqlalchemy/src/0d2e6fb5410e/examples/dynamic_dict/dynamic_dict.py?at=default
class ProxyDict(MutableMapping):
    """
    Proxies a dictionary on a relationship. This is intended for use with
    ``lazy='dynamic'`` relationships, but can also be used with regular
    InstrumentedList relationships.

    ProxyDict is used for :attr:`Node.nodes` and :attr:`Node.aliases`.

    :param parent: The instance in which this dictionary exists.
    :param collection_name: The relationship that is being proxied.
    :param childclass: The model referred to in the relationship.
    :param keyname: Attribute in childclass that will be the dictionary key.
    :param parentkey: Attribute in childclass that refers back to this parent.
    """
    def __init__(self, parent, collection_name, childclass, keyname, parentkey):
        self.parent = weakref.ref(parent)
        self.collection_name = collection_name
        self.childclass = childclass
        self.keyname = keyname
        self.parentkey = parentkey

        collection = self.collection
        if isinstance(collection, InstrumentedList):
            self.islist = True  # pragma: no cover
        else:
            self.islist = False

    @property
    def collection(self):
        return getattr(self.parent(), self.collection_name)

    def keys(self):
        if self.islist:  # pragma: no cover
            return [getattr(x, self.keyname) for x in self.collection]
        else:
            descriptor = getattr(self.childclass, self.keyname)
            return [x[0] for x in self.collection.values(descriptor)]

    def __getitem__(self, key):
        if self.islist:  # pragma: no cover
            try:
                return (i for i in self.collection if getattr(i, self.keyname) == key).next()
            except StopIteration:
                raise KeyError(key)
        else:
            item = self.collection.filter_by(**{self.keyname: key}).first()
            if item is not None:
                return item
            else:
                raise KeyError(key)

    def get(self, key, default=None):
        if self.islist:  # pragma: no cover
            try:
                return self[key]
            except KeyError:
                return default
        else:
            retval = self.collection.filter_by(**{self.keyname: key}).first()
            # Watch out for retval being falsy. Return default iff retval is None.
            if retval is None:
                return default
            else:
                return retval

    def __setitem__(self, key, value):
        try:
            existing = self[key]
            self.collection.remove(existing)
        except KeyError:
            pass
        setattr(value, self.keyname, key)
        if self.islist:  # pragma: no cover
            self.collection.append(value)
        else:
            setattr(value, self.parentkey, self.parent())

    def __delitem__(self, key):
        existing = self[key]
        if self.islist:  # pragma: no cover
            self.collection.remove(existing)
        else:
            db.session.delete(existing)  # delete-orphan doesn't trigger flush events

    def __contains__(self, key):
        if self.islist:  # pragma: no cover
            default = []
            return self.get(key, default) is not default
        else:
            return self.collection.filter_by(**{self.keyname: key}).count() > 0

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        if self.islist:  # pragma: no cover
            return len(self.collection)
        else:
            return self.collection.count()

    def __bool__(self):
        if self.islist:  # pragma: no cover
            return bool(self.collection)
        else:
            return self.collection.session.query(self.collection.exists()).first()[0]


class Node(BaseScopedNameMixin, db.Model):
    """
    Base class for all content objects.
    """
    __tablename__ = u'node'
    __title__ = u'Node'
    __type__ = u'node'
    #: Full path to this node for URL traversal
    _path = Column('path', Unicode(1000), nullable=False, default=u'')
    #: Id of the node across sites (staging, production, etc) for import/export
    buid = Column(String(22), unique=True, default=newid, nullable=False)
    user_id = Column(None, ForeignKey('user.id'), nullable=True)
    #: User who made this node, empty for auto-generated nodes
    user = relationship('User')
    _parent_id = Column('parent_id', None, ForeignKey('node.id', ondelete='CASCADE'),
        nullable=True)
    #: Parent node. If this is a root node, parent will be None. As a side effect
    #: of how SQL unique constraints work, and Nodular's own design, the value of
    #: :attr:`name` is disregarded in root nodes but cannot be blank or ``None``.
    parent = relationship('Node', remote_side='Node.id',
        primaryjoin='Node._parent_id == Node.id',
        backref=backref('_nodes', order_by='Node.name',
            cascade='all, delete-orphan',
            lazy='dynamic', passive_deletes=True))
    _root_id = Column('root_id', None, ForeignKey('node.id', ondelete='CASCADE'), nullable=True)
    _root = relationship('Node', remote_side='Node.id',
        primaryjoin='Node._root_id == Node.id', post_update=True)
    properties = Column(JsonDict, nullable=False, default={})
    #: Publication date (None until published)
    published_at = Column(DateTime, nullable=True)
    #: Type of node, for polymorphic identity
    type = Column('type', Unicode(30))
    #: Instance type, for user-customizable types
    itype = Column(Unicode(30), nullable=True)
    __table_args__ = (UniqueConstraint('parent_id', 'name'), UniqueConstraint('root_id', 'path'),
        Index('ix_node_properties', 'properties',
            postgresql_using='gin', postgresql_ops={'properties': 'jsonb_path_ops'}))
    __mapper_args__ = {'polymorphic_on': type, 'polymorphic_identity': u'node'}

    def __init__(self, **kwargs):
        with self.query.session.no_autoflush:
            super(Node, self).__init__(**kwargs)
            if self._root is None:
                self._root = self.parent or self

    def __repr__(self):
        return '<%s %s "%s">' % (self.__class__.__name__, self.path, self.title)

    @hybrid_property
    def etype(self):
        """Effective type of this instance"""
        return self.itype or self.type

    @validates('name')
    def _validate_name(self, key, value):
        try:
            assert value is not None
            assert u'/' not in value
            value = value.strip()
            assert value != u''

            if value != self.name and self.name is not None:
                alias = NodeAlias.query.get((self.parent_id, self.name))
                if alias is None:
                    alias = NodeAlias(parent=self.parent, name=self.name, node=self)
                else:
                    alias.node = self
            return value
        except AssertionError:
            raise ValueError(value)

    @validates('itype')
    def _validate_itype(self, key, value):
        if not value:
            value = None
        return value

    @hybrid_property
    def parent_id(self):
        """Container for this node (used mainly to enforce uniqueness of 'name')."""
        return self._parent_id

    @hybrid_property
    def path(self):
        """Path to this node for URL traversal."""
        return self._path

    def _update_path(self, newparent=_marker, newname=None):
        if newparent is not _marker:
            useparent = newparent
        else:
            useparent = self.parent
        if not useparent:
            self._path = u'/'  # We're root. Our name is irrelevant
        else:
            path = pathjoin(useparent.path, (newname or self.name or u''))
            if len(path) > 1000:
                raise ValueError("Path is too long")
            self._path = path
        for child in self._nodes:
            child._update_path()

    @hybrid_property
    def root(self):
        """The root node for this node's tree."""
        return self._root

    def _update_root(self, root):
        self._root = root
        for child in self._nodes:
            child._update_root(root)

    @cached_property
    def nodes(self):
        """Dictionary of all sub-nodes."""
        return ProxyDict(self, '_nodes', Node, 'name', 'parent')

    @cached_property
    def aliases(self):
        """Dictionary of all aliases for renamed, moved or deleted sub-nodes."""
        return ProxyDict(self, '_aliases', NodeAlias, 'name', 'parent')

    def getnode(self, name, default=None):
        node = self.nodes.get(name)
        if node is not None:
            alias = self.aliases.get(name)
            if alias and alias.node is not None:
                return alias.node
        return default

    def getprop(self, key, default=None):
        """Return the inherited value of a property from the closest parent node on which it was set."""
        node = self
        while node is not None:
            if key in node.properties:
                return node.properties[key]
            node = node.parent
        return default

    def as_dict(self):
        """Export the node as a dictionary."""
        return {
            'buid': self.buid,
            'name': self.name,
            'title': self.title,
            'path': self.path,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'published_at': self.published_at,
            'userid': self.user.userid if self.user else None,
            'type': self.type,
            'itype': self.itype,
        }

    def import_from(self, data):
        """Import the node from a dictionary."""
        # Do not import created_at and updated_at as they represent database-level values
        self.itype = data['itype']
        self.buid = data['buid']
        self.name = data['name']
        self.title = data['title']
        self.published_at = data['published_at']
        self.properties = data['properties']
        if data.get('userid'):
            user = Node.user.property.mapper.class_.query.filter_by(userid=data['userid']).first()
            if user:
                self.user = user

    def import_from_internal(self, data):  # pragma: no cover
        # Only required for nodes that keep internal references to other nodes.
        # This method is called in the second pass after initial import of a tree
        pass

    @classmethod
    def get(cls, buid):
        """Get a node by its buid."""
        return cls.query.filter_by(buid=buid).one_or_none()


def _node_parent_listener(target, value, oldvalue, initiator):
    """Listen for Node.parent being modified and update path"""
    if value != oldvalue:
        if value is not None:
            if target._root != value._root:
                target._update_root(value._root)
            target._update_path(newparent=value)
        else:
            # This node just got orphaned. It's a new root
            target._update_root(target)
            target._update_path(newparent=target)
    return value


def _node_name_listener(target, value, oldvalue, initiator):
    """Listen for Node.name being modified and update path"""
    if value != oldvalue:
        target._update_path(newname=value)
    return value


@event.listens_for(mapper, "mapper_configured")
def _node_mapper_listener(mapper, class_):
    if issubclass(class_, Node):
        event.listen(class_.parent, 'set', _node_parent_listener, retval=True)
        event.listen(class_.name, 'set', _node_name_listener, retval=True)


@event.listens_for(db.Session, "before_flush")
def _node_flush_listener(session, flush_context, instances=None):
    """
    When a node is deleted, make an alias that sits on the old
    name and indicates that the node has been deleted.
    """
    for obj in session._deleted.values():
        if isinstance(obj, Node) and obj.parent_id is not None:
            # Make an alias if it's a Node and it's not a root node.
            alias = NodeAlias.query.get((obj.parent_id, obj.name))
            if alias is None:
                alias = NodeAlias(parent_id=obj.parent_id, name=obj.name, node=None)
                session.add(alias)
            else:
                alias.node = None


class NodeAlias(TimestampMixin, db.Model):
    """
    When a node is renamed, it gets an alias connecting the old name to the new.
    NodeAlias makes it possible for users to rename nodes without breaking links.
    """
    #: Container id for this alias
    parent_id = Column(None, ForeignKey('node.id', ondelete='CASCADE'),
        nullable=False, primary_key=True)
    #: Container node
    parent = relationship(Node, primaryjoin=parent_id == Node.id,
        backref=backref('_aliases', lazy='dynamic',
            order_by='NodeAlias.name', cascade='all, delete-orphan'))
    #: The aliased name
    name = Column(Unicode(250), nullable=False, primary_key=True)
    #: Node id this name redirects to. If null, indicates
    #: a 410 rather than a 302 response
    node_id = Column(None, ForeignKey('node.id', ondelete='SET NULL'), nullable=True)
    #: Node this name redirects to
    node = relationship(Node, primaryjoin=node_id == Node.id,
        lazy='joined',
        backref=backref('selfaliases'))  # No cascade


class NodeMixin(PermissionMixin):
    """
    NodeMixin provides functionality for content objects to connect to the
    Node base table. NodeMixin and Node should be used together::

        class MyContentType(NodeMixin, Node):
            __tablename__ = 'my_content_type'
            my_column = Column(...)

    NodeMixin will use ``__tablename__`` as the node :attr:`~Node.type` identifier
    and will autogenerate a ``__title__`` attribute. This title is used in the UI
    when the user adds a new node.
    """
    @declared_attr
    def id(cls):
        """Link back to node"""
        return Column(None, ForeignKey('node.id', ondelete='CASCADE'),
            primary_key=True, nullable=False)

    @declared_attr
    def __mapper_args__(cls):
        """Use the table name as the polymorphic identifier"""
        return {'polymorphic_identity': cls.__tablename__}

    @declared_attr
    def __title__(cls):
        """Create a title for the type from the class name"""
        return cls.__tablename__.replace('_', ' ').title()

    @declared_attr
    def __type__(cls):
        return cls.__tablename__[:30]
