from __future__ import absolute_import, unicode_literals
# این باعث میشه هنگام شروع django، celery هم load بشه
from .celery import app as celery_app

__all__ = ('celery_app',)

