# -*- coding: utf-8 -*-

"""
Nodular's NodeMixin and Node models are the base classes for all content
objects.
"""

import os.path
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.ext.declarative import declared_attr
from coaster import newid, parse_isoformat
from coaster.sqlalchemy import TimestampMixin, PermissionMixin, BaseScopedNameMixin
from .db import db

__all__ = ['Node', 'NodeAlias', 'NodeMixin']


class Node(BaseScopedNameMixin, db.Model):
    """
    Base class for all content objects.
    """
    __tablename__ = 'node'
    #: Full path to this node for URL traversal
    path = db.Column(db.Unicode(1000), unique=True, nullable=False, default=u'')
    #: Id of the node across sites (staging, production, etc) for import/export
    buid = db.Column(db.Unicode(22), unique=True, default=newid, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    #: User who made this node, empty for auto-generated nodes
    user = db.relationship('User')
    #: Container for this node (used mainly to enforce uniqueness of 'name')
    parent_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)
    parent = db.relationship('Node', remote_side='Node.id',
                             backref=db.backref('_nodes', order_by='Node.name',
                                                cascade='all, delete-orphan'))
    #: Publication date (defaults to creation date)
    published_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    #: Type of node, for polymorphic identity
    type = db.Column('type', db.Unicode(30))
    __table_args__ = (db.UniqueConstraint('name', 'parent_id'),)
    __mapper_args__ = {'polymorphic_on': type, 'polymorphic_identity': u'node'}

    def __repr__(self):
        return u'<Node /%s "%s">' % (self.path, self.title)

    def _update_path(self, newparent=None, newname=None):
        if newparent is None and self.parent is None:
            self.path = u'/'  # We're root. Our name is irrelevant
        else:
            self.path = os.path.join((newparent or self.parent).path, (newname or self.name))
        for child in self._nodes:
            child._update_path()

    def rename(self, newname):
        """
        Rename node and make an alias linking from the old name.
        This method does not check if the new name is available.
        """
        alias = NodeAlias.query.get((self.parent_id, self.name))
        if alias is None:
            alias = NodeAlias(parent_id=self.parent_id, name=self.name, node=self)
            db.session.add(alias)
        else:
            alias.node = self
        self.name = newname

    def as_json(self):
        return {
            'buid': self.buid,
            'name': self.name,
            'title': self.title,
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
            'published_at': self.published_at.isoformat() + 'Z',
            'userid': self.user.userid,
            'type': self.type,
        }

    def import_from(self, data):
        self.uuid = data['uuid']
        self.name = data['name']
        self.title = data['title']
        self.author = data.get('author')
        self.published_at = parse_isoformat(data['published_at'])
        self.properties = data['properties']

    def import_from_internal(self, data):
        # Only required for nodes that keep internal references to other nodes
        pass


def _node_parent_listener(target, value, oldvalue, initiator):
    """Listen for Node.parent being modified and update path"""
    if value != oldvalue:
        target._update_path(newparent=value)


def _node_name_listener(target, value, oldvalue, initiator):
    """Listen for Node.name being modified and update path"""
    if value != oldvalue:
        target._update_path(newname=value)

event.listen(Node.parent, 'set', _node_parent_listener)
event.listen(Node.name, 'set', _node_name_listener)


class NodeAlias(TimestampMixin, db.Model):
    """
    When a node is renamed, it gets an alias connecting the old name to the new.
    NodeAlias makes it possible for users to rename nodes without breaking links.
    """
    #: Container id for this alias. Root nodes can't be renamed.
    parent_id = db.Column(None, db.ForeignKey('node.id'), nullable=False, primary_key=True)
    #: Container node, null for a root node
    parent = db.relationship(Node, primaryjoin=parent_id == Node.id,
                             backref=db.backref('aliases', cascade='all, delete-orphan'))
    #: The aliased name
    name = db.Column(db.Unicode(250), nullable=False, primary_key=True)
    #: Node id this name redirects to
    node_id = db.Column(None, db.ForeignKey('node.id'), nullable=False)
    #: Node this name redirects to
    node = db.relationship(Node, primaryjoin=node_id == Node.id)


class NodeMixin(TimestampMixin, PermissionMixin):
    """
    NodeMixin provides functionality for content objects to connect to the
    Node base table. NodeMixin and Node should be used together::

        class MyContentType(NodeMixin, Node):
            __tablename__ = 'my_content_type'
            my_column = db.Column(...)

    NodeMixin will use ``__tablename__`` as the node :attr:`~Node.type` identifier
    and will autogenerate a ``__title__`` attribute. This title is used in the UI
    when the user adds a new node.
    """
    @declared_attr
    def id(cls):
        """Link back to node"""
        return db.Column(None, db.ForeignKey('node.id'), primary_key=True, nullable=False)

    @declared_attr
    def __mapper_args__(cls):
        """Use the table name as the polymorphic identifier"""
        return {'polymorphic_identity': cls.__tablename__}

    @declared_attr
    def __title__(cls):
        """Create a title for the type from the class name"""
        return cls.__tablename__.replace('_', ' ').title()
