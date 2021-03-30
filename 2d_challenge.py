import socket
import time
import threading
import math
import serial
import pygame, sys
from pygame.locals import *


# Read i bytes from array as int
def int_read_from_array(array, array_index, i):
    var_bytes = array[array_index:array_index + i]
    var = hex(int.from_bytes(var_bytes, 'little'))
    return var, array_index + i


# Read i bytes from array as i chars
def char_read_from_array(array, array_index, i):
    var_bytes = array[array_index:array_index + i]
    var = str(var_bytes, 'utf-8')
    return var, array_index + i



# Reward function
def giveReward(theArduino):
    theArduino.write(b'314159265354,')


# Real time process core class
class SlideWindow():
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value

        self.num_time_stamp_0 = 0
        self.num_time_stamp_1 = 0

        self.num_last_time_stamp_0 = 0
        self.num_last_time_stamp_1 = 0

        self.time_stamp_list_0 = []
        self.time_stamp_list_1 = []

        self.sound_fre = 10
        self.slide_window = max_value * 20
        self.potential_threshold = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        self.time_above_threshold = len(self.potential_threshold) * [0.0]

    # Add time stamp to slide window
    def add_time_stamp_0(self, time_stamp):
        if self.min_value <= time_stamp <= self.max_value:
            self.num_time_stamp_0 += 1
            self.time_stamp_list_0.append(time_stamp)

    def add_time_stamp_1(self, time_stamp):
        if self.min_value <= time_stamp <= self.max_value:
            self.num_time_stamp_1 += 1
            self.time_stamp_list_1.append(time_stamp)


    # Return the number of time stamps in slide window
    def return_time_stamp_0(self):
        return self.num_time_stamp_0
    def return_time_stamp_1(self):
        return self.num_time_stamp_1

    def tcp_sync(self,new_max_value):
        self.max_value = new_max_value
        self.min_value = new_max_value - self.slide_window

        self.num_last_time_stamp_0 = self.num_time_stamp_0
        while len(self.time_stamp_list_0) != 0 and self.time_stamp_list_0[0] < self.min_value:
            self.time_stamp_list_0.remove(self.time_stamp_list_0[0])
            self.num_time_stamp_0 -= 1

        self.num_last_time_stamp_1 = self.num_time_stamp_1
        while len(self.time_stamp_list_1) != 0 and self.time_stamp_list_1[0] < self.min_value:
            self.time_stamp_list_1.remove(self.time_stamp_list_1[0])
            self.num_time_stamp_1 -= 1

# Parse neural signals sent from Intan Recorder
class ParseNeuralSignalThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global slide_window
        global channel_name
        global program_start_time
        global P1
        # Set localhost
        HOST = '127.0.0.1'

        # Connect to spike server
        spike_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        spike_socket.connect((HOST, 5002))

        # Connect to command server
        cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cmd_socket.connect((HOST, 5000))

        # Send TCP commands to set up TCP data output
        cmd_socket.sendall(
            b'set ' + channel_name_1.encode() + b'.TCPDataOutputEnabled true;set ' + channel_name_1.encode() + b'.TCPDataOutputEnabledSpike true;'+
            b'set ' + channel_name_2.encode() + b'.TCPDataOutputEnabled true;set ' + channel_name_2.encode() + b'.TCPDataOutputEnabledSpike true;'+
            b'set runmode run;')
        # cmd_socket.sendall(
        #     b'set ' + channel_name_1.encode() + b'.TCPDataOutputEnabled true;set ' + channel_name_1.encode() + b'.TCPDataOutputEnabledSpike true;'+
        #     b'set runmode run;')
        # print('Connection set up...')

        # Wait 1 second to make sure data sockets are ready to begin
        time.sleep(1)

        # Each spike chunk contains 4 bytes for magic number, 5 bytes for natice
        # channel name, 4 bytes for timestamp, and 1 byte for id. Total: 14 bytes
        bytes_per_spike_chunk = 14

        # Loop
        while True:
            spike_array = spike_socket.recv(1024)
            if spike_array == b'':
                raise RuntimeError("socket connection broken")

            if len(spike_array) > 0 and len(spike_array) % bytes_per_spike_chunk == 0:
                chunks_to_read = len(spike_array) / bytes_per_spike_chunk
                spike_index = 0
                #program_cur_time = int((time.time() - program_start_time) *20 * 1000)

                for chunk in range(int(chunks_to_read)):

                    # Make sure we get the correct magic number for this chunk
                    magic_number, spike_index = int_read_from_array(spike_array, spike_index, 4)
                    if magic_number != '0x3ae2710f':
                        print('incorrect spike magic number', magic_number)

                    # Next 5 bytes are chars of native channel name
                    native_channel_name, spike_index = char_read_from_array(spike_array, spike_index, 5)
                    # Next 4 bytes are int timestamp
                    single_timestamp, spike_index = int_read_from_array(spike_array, spike_index, 4)


                    # Next 1 byte is int id
                    single_ID, spike_index = int_read_from_array(spike_array, spike_index, 1)


                    # Calculate the firing rate
                    slide_window.tcp_sync(int(single_timestamp, 16))

                    if native_channel_name[-3:] == channel_name_1[-3:]:
                        slide_window.add_time_stamp_0(int(single_timestamp, 16))

                    if native_channel_name[-3:] == channel_name_2[-3:]:
                        slide_window.add_time_stamp_1(int(single_timestamp, 16))


# Main thread to execute the rewarding system
class MainTrialThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):

        global reward_threshold_0
        global reward_threshold_1
        global slide_window
        global P1
        global reward_condition_lock
        global total_trial_time
        global trial_start_time

        global fail_count
        global reward_count
        global trial_count

        # Loop
        f = open('./reward_count' + str(time.strftime("%m-%d", time.localtime())) + '.txt', 'w')

        trial_start_time = time.time()

        while True:
            time.sleep(0.01)

            if time.time() - program_start_time < total_trial_time:

                if time.time() - trial_start_time <= trial_period:
                    if reward_condition_lock == 0:

                        if slide_window.num_time_stamp_0 >= reward_threshold_0:
                            P1.x += 10
                            if P1.x >= 300:
                                P1.x -= 10

                        if slide_window.num_time_stamp_0 >= reward_threshold_1:
                            P1.y += 10
                            if P1.y >= 300:
                                P1.y -= 10

                elif trial_period < time.time() - trial_start_time < trial_period + 5:

                    if reward_condition_lock == 0:
                        fail_count += 1
                        print('{} Success : {} Time Out (Time Out in Last Trial)'.format(reward_count, fail_count))
                        P1.x = 0
                        P1.y = 0
                        time.sleep(5)

                else:
                    trial_count += 1
                    trial_start_time = time.time()
                    reward_condition_lock = 0

            else:
                print('Total {} seconds task finished, waiting for release'.format(total_trial_time))
                f.writelines('threshold 1: ' + str(reward_threshold_1) + '\n')
                f.writelines('trial_period: ' + str(trial_period) + '\n')
                f.writelines('total_trial_time: ' + str(total_trial_time) + '\n')
                f.writelines('reward_count: ' + str(reward_count) + '\n')
                f.close()
                break


# Receive signals from Arduino
class Listen2ArduinoThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global reward_condition_lock
        global arduino
        global trial_start_time
        while True:
            time.sleep(0.002)

            # If the is ready for next trial
            if arduino.read_until(b','):
                reward_condition_lock = 0
                trial_start_time = time.time()

class Square(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        #self.image = pygame.image.load('player.bmp')
        self.x = 0
        self.y = 0

    def update(self):
        # pressed_keys = pygame.key.get_pressed()
        #
        # if pressed_keys[K_UP]:
        #     self.x += 50
        #     if self.x > 300:
        #         self.x -= 50
        #
        # if pressed_keys[K_DOWN]:
        #     self.y += 50
        #     if self.y > 300:
        #         self.y -= 50
        global arduino
        global reward_condition_lock
        global reward_count
        global trial_count
        if self.y >=300 and self.x >=300:
            reward_condition_lock = 1
            giveReward(arduino)
            reward_count += 1
            trial_count += 1
            print('{} Success : {} Time Out (Success in Last Trial)'.format(reward_count, fail_count))
            self.y =0
            self.x =0

    def draw(self, surface):
        #surface.blit(self.image, dest=(self.x,self.y))
        pygame.draw.rect(surface, (255,255,255), (self.x,self.y,100,100))


class Goal(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        #self.image = pygame.image.load('background.bmp')
        #self.surf = pygame.Surface((100,100))
    def draw(self, surface):
        #surface.blit(self.image, dest=(400,400))
        pygame.draw.rect(surface,(255,255,255), (300,300,100,100))


class RewardMap(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global P1

        pygame.init()

        FPS = 20
        FramePerSec = pygame.time.Clock()

        BLACK = (0, 0, 0)

        DISPLAYSURF = pygame.display.set_mode((400, 400))
        DISPLAYSURF.fill(BLACK)

        while True:
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()

            P1.update()
            goal.update()

            DISPLAYSURF.fill(BLACK)
            goal.draw(DISPLAYSURF)
            P1.draw(DISPLAYSURF)

            #pygame.draw.rect(DISPLAYSURF,(128,0,0),(350,350,100,100))
            #pygame.draw.rect(DISPLAYSURF,(0,128,0),(P1.x, P1.y,100,100))

            pygame.display.update()
            FramePerSec.tick(FPS)

# Initialize trial time
trial_start_time = time.time()

# A lock to avoid conflict
reward_condition_lock = 0

fail_count = 0
reward_count = 0
trial_count = 0

###############Initial Settings##########
# Arduino serial port, you can know this from Arduino->Tools->Port
# It is usually 'COM3' in Windows and '/dev/cu.usbXXXX' in MacOS
serial_port = 'COM3'

# Baud rate between Arduino and PC
baud_rate = 115200
arduino = serial.Serial(serial_port, baud_rate)

# You can always choose a proper channel name by editing the following line
channel_name_1 = 'c-069'
channel_name_2 = 'c-114'

# Set a threshold
reward_threshold_0 = 11
reward_threshold_1 = 10

# Time for a trial
trial_period = 30

# Total training time
total_trial_time = 300

# Define the lowest and highest sound frequency for the mouse
low_frequency = 8000
high_frequency = 24000
#############End of Initial Settings#######

#############Execute the Program###########
slide_window = SlideWindow(0, 200)

P1 = Square()
goal = Goal()

reward_map = RewardMap()
reward_map.start()

time.sleep(3)

# Instantiate
main_trial_thread = MainTrialThread()
parse_neural_signal_thread = ParseNeuralSignalThread()
listen2arduino_thread = Listen2ArduinoThread()

# Start the program

program_start_time = time.time()
parse_neural_signal_thread.start()
main_trial_thread.start()
listen2arduino_thread.start()


