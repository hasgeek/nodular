# -*- coding: utf-8 -*-

import os
import unittest
from flask import Flask
from coaster.utils import buid
from coaster.sqlalchemy import BaseMixin
from nodular.db import db


class User(BaseMixin, db.Model):
    __tablename__ = 'user'
    userid = db.Column(db.Unicode(22), nullable=False, default=buid, unique=True)
    username = db.Column(db.Unicode(250), nullable=True)


app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SQLALCHEMY_DATABASE_URI', 'postgresql://postgres@localhost/myapp_test')
app.config['SQLALCHEMY_ECHO'] = False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
db.app = app


class TestDatabaseFixture(unittest.TestCase):
    def setUp(self):
        self.app = app
        db.create_all()
        self.user1 = User(username=u'user1')
        db.session.add(self.user1)
        app.testing = True

    def tearDown(self):
        db.session.rollback()
        db.drop_all()
        db.session.remove()
