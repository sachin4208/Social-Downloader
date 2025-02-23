from app import celery, app

if __name__ == '__main__':
    celery.worker_main(['worker', '--loglevel=info'])