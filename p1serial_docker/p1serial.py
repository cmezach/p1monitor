#!/usr/bin/python3

# This script will read data from serial connected to the digital meter P1 port

# Created by Jens Depuydt
# https://www.jensd.be
# https://github.com/jensdepuydt
import time
import serial
import sys
import crcmod.predefined
import re
import json
from influxdb import InfluxDBClient


#Configure InfluxDB connection variables
host = "influxdb"  # My Ubuntu NUC
port = 8086  # default port
user = "admin"  # the user/password created for the pi, with write access
password = "admin"
dbname = "p1data" # the database we created earlier
interval = 10 # Sample period in seconds

# Create the InfluxDB client object
client = InfluxDBClient(host, port, user, password, dbname)

# Change your serial port here:
serialport = '/dev/ttyUSB0'

# Enable debug if needed:
debug = 0
# Add/update OBIS codes here:
obiscodes = {
    "0-0:1.0.0": "Timestamp",
#    "0-0:96.3.10": "Switch electricity",
#    "0-1:24.4.0": "Switch gas",
#    "0-0:96.1.1": "Meter serial electricity",
#    "0-1:96.1.1": "Meter serial gas",
    "0-0:96.14.0": "current_rate",
    "1-0:1.8.1": "dalverbruik",
    "1-0:1.8.2": "piekverbruik",
#    "1-0:2.8.1": "Rate 1 (day) - total production",
#    "1-0:2.8.2": "Rate 2 (night) - total production",
#    "1-0:21.7.0": "L1 consumption",
#    "1-0:41.7.0": "L2 consumption",
#    "1-0:61.7.0": "L3 consumption",
    "1-0:1.7.0": "vermogenaf",
#    "1-0:22.7.0": "L1 production",
#    "1-0:42.7.0": "L2 production",
#    "1-0:62.7.0": "L3 production",
#    "1-0:2.7.0": "All phases production",
    "1-0:32.7.0": "spanning",
#    "1-0:52.7.0": "L2 voltage",
#    "1-0:72.7.0": "L3 voltage",
#    "1-0:31.7.0": "L1 current",
#    "1-0:51.7.0": "L2 current",
#    "1-0:71.7.0": "L3 current",
#    "0-1:24.2.3": "Gas consumption"
    }


def checkcrc(p1telegram):
    # check CRC16 checksum of telegram and return False if not matching
    # split telegram in contents and CRC16 checksum (format:contents!crc)
    for match in re.compile(b'\r\n(?=!)').finditer(p1telegram):
        p1contents = p1telegram[:match.end() + 1]
        # CRC is in hex, so we need to make sure the format is correct
        givencrc = hex(int(p1telegram[match.end() + 1:].decode('ascii').strip(),                                                                                                              16))
    # calculate checksum of the contents
    calccrc = hex(crcmod.predefined.mkPredefinedCrcFun('crc16')(p1contents))
    # check if given and calculated match
    if debug:
        print(f"Given checksum: {givencrc}, Calculated checksum: {calccrc}")
    if givencrc != calccrc:
        if debug:
            print("Checksum incorrect, skipping...")
        return False
    return True


def parsetelegramline(p1line):
    # parse a single line of the telegram and try to get relevant data from it
    unit = ""
    timestamp = ""
    if debug:
        print(f"Parsing:{p1line}")
    # get OBIS code from line (format:OBIS(value)
    obis = p1line.split("(")[0]
    if debug:
        print(f"OBIS:{obis}")
    # check if OBIS code is something we know and parse it
    if obis in obiscodes:
        # get values from line.
        # format:OBIS(value), gas: OBIS(timestamp)(value)
        values = re.findall(r'\(.*?\)', p1line)
        value = values[0][1:-1]
        # timestamp requires removal of last char
        if obis == "0-0:1.0.0" or len(values) > 1:
            value = value[:-1]
        # report of connected gas-meter...
        if len(values) > 1:
            timestamp = value
            value = values[1][1:-1]
        # serial numbers need different parsing: (hex to ascii)
        if "96.1.1" in obis:
            value = bytearray.fromhex(value).decode()
        else:
            # separate value and unit (format:value*unit)
            lvalue = value.split("*")
            value = float(lvalue[0])
            if len(lvalue) > 1:
                unit = lvalue[1]
        # return result in tuple: description,value,unit,timestamp
        if debug:
            print (f"description:{obiscodes[obis]}, \
                     value:{value}, \
                     unit:{unit}")
        return (obiscodes[obis], value, unit)
    else:
        return ()


def main():
    ser = serial.Serial(serialport, 115200, xonxoff=1)
    p1telegram = bytearray()
    while True:
        try:
            # read input from serial port
            p1line = ser.readline()
            if debug:
                print ("Reading: ", p1line.strip())
            # P1 telegram starts with /
            # We need to create a new empty telegram
            if "/" in p1line.decode('ascii'):
                p1telegram = bytearray()
            # add line to complete telegram
            p1telegram.extend(p1line)
            # P1 telegram ends with ! + CRC16 checksum
            if "!" in p1line.decode('ascii'):
                if checkcrc(p1telegram):
                    # parse telegram contents, line by line
                     emptyjson = '[{"measurement" : "p1-stroom" , "fields" : {}}                                                                                                             ]'
                     data = json.loads(emptyjson)
                     for line in p1telegram.split(b'\r\n'):
                         r = parsetelegramline(line.decode('ascii'))
                         if r:
                           data[0]['fields'][r[0]] = r[1]
                     formatted_output = json.dumps(data)
                     print (formatted_output)
                     client.write_points(data)
                     time.sleep(10)
        except KeyboardInterrupt:
            print("Stopping...")
            ser.close()
            break
#        except:
#            if debug:
#                print(traceback.format_exc())
#            # print(traceback.format_exc())
#            print ("Something went wrong...")
#            ser.close()
#        # flush the buffer
#        ser.flush()

if __name__ == '__main__':
    main()
