# -*- coding: utf-8 -*-

"""
Nodular's NodeMixin and Node models are the base classes for all content
objects.
"""

import weakref
from datetime import datetime
from collections import MutableMapping
from werkzeug import cached_property
import simplejson as json

from sqlalchemy import Column, Integer, String, Unicode, DateTime
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy import event
from sqlalchemy.orm import validates, mapper, relationship, backref
from sqlalchemy.orm.collections import InstrumentedList, attribute_mapped_collection
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from coaster import newid, parse_isoformat
from coaster.sqlalchemy import TimestampMixin, PermissionMixin, BaseScopedNameMixin

from .db import db

__all__ = ['Node', 'NodeAlias', 'NodeMixin', 'ProxyDict', 'pathjoin']


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
        if b.startswith('/'):
            path = b
        elif path == '' or path.endswith('/'):
            path += b
        else:
            path += '/' + b
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
            return self.collection.filter_by(**{self.keyname: key}).first() or default

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


class Property(TimestampMixin, db.Model):
    __tablename__ = 'property'
    node_id = db.Column(None, db.ForeignKey('node.id', ondelete='CASCADE'),
        nullable=False, primary_key=True)
    name = db.Column(db.Unicode(40), nullable=False, primary_key=True)
    _value = db.Column('value', db.Unicode(1000), nullable=False)

    # value is NOT a synonym for _value (using SQLAlchemy's synonym) because
    # it stores an encoded value and can't be used directly for queries.
    @property
    def value(self):
        if not hasattr(self, '_cached_value'):
            try:
                self._cached_value = json.loads(self._value, use_decimal=True)
            except json.JSONDecodeError:
                # The database somehow had an invalid value. Don't use this value
                self._cached_value = None
        return self._cached_value

    @value.setter
    def value(self, value):
        setval = unicode(json.dumps(value))
        if len(setval) > 1000:
            raise ValueError("Value is too long")
        self._value = setval
        self._cached_value = value


class Node(BaseScopedNameMixin, db.Model):
    """
    Base class for all content objects.
    """
    __tablename__ = u'node'
    __title__ = u'Node'
    __type__ = u'node'
    #: Full path to this node for URL traversal
    _path = Column('path', Unicode(1000), unique=True, nullable=False, default=u'')
    #: Id of the node across sites (staging, production, etc) for import/export
    buid = Column(String(22), unique=True, default=newid, nullable=False)
    user_id = Column(None, ForeignKey('user.id'), nullable=True)
    #: User who made this node, empty for auto-generated nodes
    user = relationship('User')
    _parent_id = Column('parent_id', Integer, ForeignKey('node.id', ondelete='CASCADE'),
        nullable=True)
    parent = relationship('Node', remote_side='Node.id',
        backref=backref('_nodes', order_by='Node.name',
            cascade='all, delete-orphan',
            lazy='dynamic', passive_deletes=True))
    _properties = relationship(Property, cascade='all, delete-orphan', backref='node',
        collection_class=attribute_mapped_collection('name'))
    #: Dictionary of ``{name: value}`` pairs attached to this node
    #: where ``name`` is a string (up to 40 chars) and ``value`` is any
    #: JSON-serializable value (up to 1000 chars)
    properties = association_proxy('_properties', 'value',
        creator=lambda k, v: Property(name=k, value=v))
    #: Publication date (defaults to creation date)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: Type of node, for polymorphic identity
    type = Column('type', Unicode(30))
    __table_args__ = (UniqueConstraint('name', 'parent_id'),)
    __mapper_args__ = {'polymorphic_on': type, 'polymorphic_identity': u'node'}

    def __repr__(self):
        return u'<Node %s "%s">' % (self.path, self.title)

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

    @hybrid_property
    def parent_id(self):
        """Container for this node (used mainly to enforce uniqueness of 'name')"""
        return self._parent_id

    @hybrid_property
    def path(self):
        """Path to this node for URL traversal"""
        return self._path

    def _update_path(self, newparent=None, newname=None):
        if not newparent and not self.parent:
            self._path = u'/'  # We're root. Our name is irrelevant
        else:
            path = pathjoin((newparent or self.parent).path, (newname or self.name or u''))
            if len(path) > 1000:
                raise ValueError("Path is too long")
            self._path = path
        for child in self._nodes:
            child._update_path()

    @cached_property
    def nodes(self):
        """Dictionary of all sub-nodes."""
        return ProxyDict(self, '_nodes', Node, 'name', 'parent')

    @cached_property
    def aliases(self):
        """Dictionary of all aliases for renamed nodes."""
        return ProxyDict(self, '_aliases', NodeAlias, 'name', 'parent')

    def getprop(self, key, default=None):
        """Return the inherited value of a property from the closest parent node on which it was set."""
        node = self
        while node is not None:
            if key in node.properties:
                return node.properties[key]
            node = node.parent
        return default

    def as_json(self):
        return {
            'buid': self.buid,
            'name': self.name,
            'title': self.title,
            'path': self.path,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
            'published_at': self.published_at.isoformat() + 'Z',
            'userid': self.user.userid if self.user else None,
            'type': self.type,
        }

    def import_from(self, data):
        self.uuid = data['uuid']
        self.name = data['name']
        self.title = data['title']
        self.author = data.get('author')
        self.published_at = parse_isoformat(data['published_at'])
        self.properties = data['properties']

    def import_from_internal(self, data):  # pragma: no cover
        # Only required for nodes that keep internal references to other nodes
        pass


def _node_parent_listener(target, value, oldvalue, initiator):
    """Listen for Node.parent being modified and update path"""
    if value != oldvalue and value is not None:
        target._update_path(newparent=value)
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
        return cls.__tablename__
