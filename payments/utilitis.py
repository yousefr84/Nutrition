import random


def generate_unique_pid(model_class):
    while True:
        pid = random.randint(100000, 999999)
        if not model_class.objects.filter(pid=pid).exists():
            return pid
