from flask import Flask
from threading import Thread

class CustomFlask(Flask):

    def __init__(self, import_name, background_task):
        super().__init__(import_name)
        t = Thread(target=background_task)
        t.start()