# -*- coding: utf-8 -*-

"""
Nodular provides a Flask-SQLAlchemy database object that all models in
your app must use. Typical usage::

    from nodular import db
    from coaster.sqlalchemy import BaseMixin

    class MyModel(BaseMixin, db.Model):
        pass

To initialize with an app::

    from flask import Flask
    app = Flask(__name__)
    db.init_app(app)

If you have only one app per Python process (which is typical), add
this line to your init sequence::

    db.app = app

This makes your app the default app for this database object and removes
the need to use ``app.test_request_context()`` when querying the database
outside a request context.
"""

from flask.ext.sqlalchemy import SQLAlchemy

__all__ = ['db']

db = SQLAlchemy()
