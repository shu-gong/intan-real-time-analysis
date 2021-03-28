import time
from pyfirmata import Arduino
import threading

class M():
    def __init__(self, fre):
        self.fre = fre
    def myfre(self):
        time.sleep(7)
        #for i in range(10):
        #    self.fre = self.fre / 2**(i+1)
        #    time.sleep(0.5)

m = M(0.005)


class thread1(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global m
        m.myfre()
        print(m.fre)

class SlideWindowBear():
    def __init__(self, left_hand, right_hand):
        self.left_hand = left_hand
        self.right_hand = right_hand
        self.num_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 10
        self.slide_window = right_hand * 20

    def eat(self, time_stamp):
        if time_stamp > self.left_hand and time_stamp < self.right_hand:
            self.num_time_stamp += 1
            self.time_stamp_list.append(time_stamp)

    def clean(self):
        if len(self.time_stamp_list) != 0 and self.time_stamp_list[0] < self.left_hand:
            self.time_stamp_list.remove(self.time_stamp_list[0])
            self.num_time_stamp -= 1
        #if self.num_time_stamp != 0:
        #    print('#############################################################################',self.num_time_stamp)

    def move(self, new_right_hand):
        if new_right_hand > self.slide_window:
            self.right_hand = new_right_hand
            self.left_hand = new_right_hand - self.slide_window

    def talk(self):
        # Calculate sound frequency
        if self.num_time_stamp == 0:
            return 100
        else:
            self.sound_fre = 2**(self.num_time_stamp)
            return 1000*self.sound_fre
slide_window_bear = SlideWindowBear(0, 400)

class thread2(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        board = Arduino('/dev/cu.usbmodem1401')
        global m
        while True:
            #time.sleep(5e-06)
            board.digital[7].write(1)
            time.sleep(0.5/slide_window_bear.talk())
            board.digital[7].write(0)
            time.sleep(0.5/slide_window_bear.talk())


class thread3(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global start_time
        while True:
            print(int((time.time()-start_time)*1000))


start_time = time.time()


#t1 = thread1()
t2 = thread2()
#t3 = thread3()
#t1.start()
t2.start()
#t3.start()



'''
board = Arduino('/dev/cu.usbmodem11401')
while True:
    board.digital[7].write(1)
    time.sleep(1)
    board.digital[7].write(0)
    time.sleep(1)
'''