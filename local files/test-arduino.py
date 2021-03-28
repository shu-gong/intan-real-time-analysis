
import time
from pyfirmata import Arduino
import threading

m = 0.5

class thread1(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	def run(self):
		global m
		time.sleep(3)
		m = 3


class thread2(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	def run(self):
		board = Arduino('/dev/cu.usbmodem11401')
		while True:
			board.digital[6].write(1)
			time.sleep(0.0002)
			board.digital[6].write(0)
			time.sleep(0.0001)


#t1 = thread1()
t2 = thread2()

#t1.start()
t2.start()