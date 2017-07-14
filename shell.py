#!/usr/bin/env python
import os
try:
    import readline  # NOQA
except ImportError:
    pass
from pprint import pprint  # NOQA
from coaster.sqlalchemy import BaseMixin
from coaster.utils import buid

from flask import Flask
from nodular import *  # NOQA


class User(BaseMixin, db.Model):
    __tablename__ = 'user'
    userid = db.Column(db.Unicode(22), nullable=False, default=buid, unique=True)
    username = db.Column(db.Unicode(250), nullable=True)


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SQLALCHEMY_DATABASE_URI', 'sqlite://')
app.config['SQLALCHEMY_ECHO'] = False
db.init_app(app)
db.app = app

root = Node(name=u'root', title=u'Root')
db.session.add(root)

os.environ['PYTHONINSPECT'] = 'True'
