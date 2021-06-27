from common.models import *

if __name__ == '__main__':
    db.create_tables([Photo, User, Task, TaskWorker, Request, Invoice])