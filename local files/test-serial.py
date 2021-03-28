import serial
import time

arduino = serial.Serial('/dev/cu.usbmodem11401', 115200)
'''
while True:
    fre = input("tell me your frequency")
    gap = 500000 / int(fre)
    b = (str(gap)+',').encode()
    arduino.write(b)
'''
while True:
    if arduino.read_until(b','):
        print('hh')

