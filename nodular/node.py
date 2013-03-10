# -*- coding: utf-8 -*-

from datetime import datetime
from flask import g
from sqlalchemy.ext.declarative import declared_attr
from coaster import newid, parse_isoformat
from coaster.sqlalchemy import TimestampMixin, PermissionMixin, BaseScopedNameMixin
from baseframe.sqlalchemy import db

__all__ = ['Node', 'NodeTree', 'NodeAlias', 'NodeMixin']


def default_user_id():
    return g.user.id if g.user else None


class Node(BaseScopedNameMixin, db.Model):
    __tablename__ = 'node'
    #: Id of the node across sites (staging, production, etc) for import/export
    buid = db.Column(db.Unicode(22), unique=True, default=newid, nullable=False)
    #: User who made this node
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, default=default_user_id)
    user = db.relationship('User')
    #: Container for this node (used mainly to enforce uniqueness of 'name')
    parent_id = db.Column(db.Integer, db.ForeignKey('node.id'), nullable=True)
    nodes = db.relationship('Node', backref=db.backref('parent', remote_side='Node.id'),
                            order_by='Node.name', cascade='all, delete-orphan')
    #: Publication date
    published_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    #: Type of node, for polymorphic identity
    type = db.Column('type', db.Unicode(30))
    __table_args__ = (db.UniqueConstraint('name', 'parent_id'),)
    __mapper_args__ = {'polymorphic_on': type, 'polymorphic_identity': u'node'}

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

    def detach(self):
        """
        TODO: Detach node from the tree.
        """
        self.parent = None
        # TODO: Update NodeTree

    def attach(self, node):
        """
        TODO: Make this node a child of the specified node.
        """
        self.detach()
        if node is not None:
            self.parent = node
            # TODO: Update NodeTree

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


class NodeTree(TimestampMixin, db.Model):
    """
    NodeTree implements a closure set structure to help navigate the node tree rapidly.
    """
    __tablename__ = 'node_tree'
    #: Parent node id
    parent_id = db.Column(None, db.ForeignKey('node.id'), nullable=False, primary_key=True)
    #: Parent node
    parent = db.relationship(Node, primaryjoin=parent_id == Node.id,
                             backref=db.backref('childtree',
                                                cascade='all, delete-orphan'))
    #: Child node id
    child_id = db.Column(None, db.ForeignKey('node.id'), nullable=False, primary_key=True)
    #: Child comment
    child = db.relationship(Node, primaryjoin=child_id == Node.id,
                            backref=db.backref('parenttree',
                                               cascade='all, delete-orphan'))
    #: Distance from parent to child in the hierarchy
    depth = db.Column(db.SmallInteger, nullable=False)


class NodeAlias(TimestampMixin, db.Model):
    """
    When a node is renamed, it gets an alias connecting the old name to the new.
    """
    #: Container id for this alias
    parent_id = db.Column(None, db.ForeignKey('node.id'), nullable=True, primary_key=True)
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
        """Create a title for the type, from the class name"""
        return cls.__tablename__.replace('_', ' ').title()
