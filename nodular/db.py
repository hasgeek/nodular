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


# To enable foreign key support in SQLite3
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlite3 import Connection as SQLite3Connection


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()
