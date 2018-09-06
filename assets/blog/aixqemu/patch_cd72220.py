import sys
patch_off = 0x7b43800
patch_data = b"#!/bin/sh\n/bin/sh\nexit\n"
with open(sys.argv[1], "rb") as infile:
	indata = bytearray(infile.read())
indata[patch_off:patch_off+len(patch_data)] = patch_data
with open(sys.argv[2], "wb") as outfile:
	outfile.write(indata)
