# -*- coding: utf-8 -*-

"""
Database root class.
"""

from flask.ext.sqlalchemy import SQLAlchemy

__all__ = ['db']

db = SQLAlchemy()
