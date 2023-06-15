import psutil
import os
import time
from psutil import NoSuchProcess

try:
    TARGET = "chrome.exe"
    [process.kill() for process in psutil.process_iter() if process.name() == TARGET]
except NoSuchProcess:
    print('Браузера закрыты.')
finally:
    time.sleep(5)
    os.system('main.py')
