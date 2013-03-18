# -*- coding: utf-8 -*-

"""
Nodular's RevisionedNodeMixin base class helps make models with revisioned
content.
"""

__all__ = ['RevisionedNodeMixin']

from sqlalchemy import Column, ForeignKey, UniqueConstraint, Unicode, SmallInteger
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, backref
from coaster.sqlalchemy import BaseMixin

from .node import NodeMixin


class RevisionedNodeMixin(NodeMixin):
    """
    RevisionedNodeMixin replaces NodeMixin for models that need to keep their
    entire contents under revision control. A revisioned node can have multiple
    simultaneously active versions (each with a label) or archived versions
    (unlabeled) for editing history reference.

    Revisions are stored as distinct table rows with full content, not as diffs.
    All columns that need revisioning must be in the :class:`RevisionMixin`
    model, not in the :class:`RevisionedNodeMixin` model. Usage::

        class MyDocument(RevisionedNodeMixin, Node):
            __tablename__ = u'my_document'


        class MyDocumentRevision(MyDocument.RevisionMixin, db.Model):
            content = db.Column(db.UnicodeText, nullable=False, default=u'')
            ...
    """

    #: Current primary revision for web publishing (to regular unauthenticated users)
    # @declared_attr
    # def primary_id(cls):
    #     return Column(None, ForeignKey(cls.__tablename__ + '_revisions.id',
    #         use_alter=True, name='fk_' + cls.__tablename__ + '_primary_id'), nullable=True)

    @declared_attr
    def RevisionMixin(cls):
        parentclass = cls
        tablename = parentclass.__tablename__ + '_revisions'

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
                return relationship(parentclass, backref=backref('revisions', lazy='dynamic', cascade='all, delete-orphan'))

            @declared_attr
            def language(cls):
                """
                Language for this revision.
                """
                return Column(Unicode(5), nullable=False, default=u'')

            @declared_attr
            def status(cls):
                """
                Status code for this revision.
                """
                return Column(SmallInteger, nullable=True)

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
                return Column(None, ForeignKey(tablename + '.id'), nullable=True)

            @declared_attr
            def previous(cls):
                """
                Parent revision.
                """
                return relationship(cls)

            @declared_attr
            def __table_args__(cls):
                return (UniqueConstraint('node_id', 'language', 'status'),)

            def copy(self):
                """
                Return a copy of self.
                """
                raise NotImplementedError
                revision = self.__class__(previous=self)
                return revision

        return RevisionMixin

    def revise(self, revision=None, user=None):
        """
        Clone the given revision or make a new blank revision.
        """
        if revision is not None:
            assert isinstance(revision, self.__revision_model__)
            newrevision = revision.copy()
            newrevision.node = self
            newrevision.user = user
            return newrevision
        else:
            return self.__revision_model__(node=self, user=user)
