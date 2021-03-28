
import time
from pyfirmata import Arduino
import threading

class thread1(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global testpara
        if testpara == 0:
            con.acquire()
            time.sleep(3)
            print('threading11111')
            con.release()


class thread2(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        if con.acquire():
            time.sleep(1)
            print('threading222222')
            con.release()

class thread3(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        if con2.acquire():
            time.sleep(1)
            print('threading33333')
            con2.release()

con = threading.Condition()
#con2 = threading.Condition()
testpara = 0

t1 = thread1()
t2 = thread2()
#t3 = thread3()

t1.start()
t2.start()
#t3.start()