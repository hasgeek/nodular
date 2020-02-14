# -*- coding: utf-8 -*-

"""
Nodular's RevisionedNodeMixin base class helps make models with revisioned
content.
"""

__all__ = ['RevisionedNodeMixin']

from werkzeug.utils import cached_property
from sqlalchemy import Column, ForeignKey, UniqueConstraint, Unicode
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, backref
from coaster.sqlalchemy import BaseMixin

from .db import db
from .node import NodeMixin, ProxyDict


class RevisionedNodeMixin(NodeMixin):
    """
    RevisionedNodeMixin replaces NodeMixin for models that need to keep their
    entire contents under revision control. A revisioned node can have multiple
    simultaneously active versions (each with a label) or archived versions
    (label=None).

    Revisions are stored as distinct table rows with full content, not as diffs.
    All columns that need revisioning must be in the :class:`RevisionMixin`
    model, not in the :class:`RevisionedNodeMixin` model. Usage::

        class MyDocument(RevisionedNodeMixin, Node):
            __tablename__ = u'my_document'


        class MyDocumentRevision(MyDocument.RevisionMixin, db.Model):
            # __tablename__ is auto-generated
            content = db.Column(db.UnicodeText)
            ...
    """

    #: Current primary revision for web publishing (to regular unauthenticated users)
    # @declared_attr
    # def primary_id(cls):
    #     return Column(None, ForeignKey(cls.__tablename__ + '_revision.id',
    #         use_alter=True, name='fk_' + cls.__tablename__ + '_primary_id'), nullable=True)

    @declared_attr
    def RevisionMixin(cls):
        parentclass = cls
        tablename = parentclass.__tablename__ + '_revision'

        class RevisionMixin(BaseMixin):
            """
            RevisionMixin is the baseclass for revisioned models.
            """
            @declared_attr
            def __parent_model__(cls):
                """Parent model whose content is being revisioned"""
                parentclass.__revision_model__ = cls
                # parentclass.primary = relationship(cls,
                #     primaryjoin=parentclass.primary_id == cls.id,
                #     post_update=True)
                return parentclass

            @declared_attr
            def __tablename__(cls):
                if '_cached_tablename' in cls.__dict__:
                    return cls._cached_tablename
                else:
                    return tablename

            @declared_attr
            def node_id(cls):
                return Column(None, ForeignKey(parentclass.__tablename__ + '.id', ondelete='CASCADE'),
                    nullable=False)

            @declared_attr
            def node(cls):
                """
                Link back to node
                """
                parentclass.workflow_revision = cached_property(lambda self: ProxyDict(
                    self, 'revisions', cls, 'workflow_label', 'node'))
                return relationship(parentclass, backref=backref('revisions', lazy='dynamic', cascade='all, delete-orphan'))

            @declared_attr
            def workflow_label(cls):
                """
                Label for this revision.
                """
                return Column(Unicode(20), nullable=True)

            @declared_attr
            def user_id(cls):
                return Column(None, ForeignKey('user.id'), nullable=True)

            @declared_attr
            def user(cls):
                """
                User who made this revision.
                """
                return relationship('User')

            @declared_attr
            def previous_id(cls):
                return Column(None, ForeignKey(cls.__tablename__ + '.id'), nullable=True)

            @declared_attr
            def previous(cls):
                """
                Parent revision.
                """
                return relationship(cls,
                    primaryjoin=cls.__name__ + '.previous_id == ' + cls.__name__ + '.id',
                    uselist=False)

            @declared_attr
            def __table_args__(cls):
                return (UniqueConstraint('node_id', 'workflow_label'),)

            def copy(self):
                """
                Return a copy of self. Subclasses must override this to copy the actual content
                of the model.
                """
                revision = self.__class__(
                    node=self.node,
                    workflow_label=None,  # Label cannot be copied
                    user=self.user,
                    previous=self.previous)
                return revision

        return RevisionMixin

    def revise(self, revision=None, user=None, workflow_label=None):
        """
        Clone the given revision or make a new blank revision.

        :returns: New revision object
        """
        if workflow_label is not None:
            rev = self.workflow_revision.get(workflow_label)
            if rev is not None:
                rev.workflow_label = None
                # We have to flush here or the SQL UPDATE statement
                # for the above line gets called *after* the INSERT statement
                # for the new revision below, resulting in an IntegrityError
                db.session.flush()
        if revision is not None:
            assert isinstance(revision, self.__revision_model__)
            newrevision = revision.copy()
            newrevision.previous = revision
            newrevision.workflow_label = workflow_label
            return newrevision
        else:
            return self.__revision_model__(node=self, user=user, workflow_label=workflow_label)

    def set_workflow_label(self, revision, workflow_label):
        """
        Set the workflow label for the given revision.
        """
        if workflow_label is not None:
            rev = self.workflow_revision.get(workflow_label)
            if rev is not None:
                rev.workflow_label = None
        revision.workflow_label = workflow_label
