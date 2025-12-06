# Taghzieh/celery.py
import os
import logging
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Taghzieh.settings')

app = Celery('Taghzieh')

# خواندن تنظیمات CELERY_ از settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# اتصال مطمئن به broker
app.conf.broker_connection_retry_on_startup = True

# تنظیمات عمومی
app.conf.update(
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_acks_on_failure_or_timeout=False,
    result_expires=3600,   # نتایج بعد از یک ساعت پاک شوند
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
)

# لاگینگ ساده
app.conf.task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
app.conf.worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    filename='celery.log',  # اختیاری: اگر نمی‌خواهی فایل ساخته بشه، این خط رو بردار
)

# کشف اتوماتیک تسک‌ها
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
