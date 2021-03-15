import threading
import time
marker = 0

class thread1(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global marker
        while True:
            marker += 1

class thread2(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global marker
        while True:
            if marker%2 == 0:
                print('green')
            else:
                print('red')

t1 = thread1()
t2 = thread2()
t2.start()
t1.start()
