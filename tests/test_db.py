# -*- coding: utf-8 -*-

import unittest
from flask import Flask
from coaster import newid
from coaster.sqlalchemy import BaseMixin
from baseframe.sqlalchemy import db


class User(BaseMixin, db.Model):
    __tablename__ = 'user'
    userid = db.Column(db.Unicode(22), nullable=False, default=newid, unique=True)
    username = db.Column(db.Unicode(250), nullable=True)


app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres@localhost/myapp_test'  # 'sqlite://'
app.config['SQLALCHEMY_ECHO'] = True
db.init_app(app)
db.app = app


class TestDatabaseFixture(unittest.TestCase):
    def setUp(self):
        db.create_all()
        self.user1 = User(username=u'user1')
        db.session.add(self.user1)

    def tearDown(self):
        db.session.rollback()
        db.drop_all()


if __name__ == '__main__':
    unittest.main()
