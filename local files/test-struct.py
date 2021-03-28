import os, struct
mydat = b'\x0fq\xe2:D-092\xe0\xd2\x00\x00\x01'
magicNumber, = struct.unpack('<I', mydat.read(4))
print(magicNumber)