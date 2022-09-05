#!/usr/bin/env python

# SI4703 Python Library
# 

import smbus
import time
import RPi.GPIO as GPIO
import array as buffer


class si4703Radio():
    # Define the register names
    SI4703_DEVICEID = 0x00
    SI4703_CHIPID = 0x01
    SI4703_POWERCFG = 0x02
    SI4703_CHANNEL = 0x03
    SI4703_SYSCONFIG1 = 0x04
    SI4703_SYSCONFIG2 = 0x05
    SI4703_SYSCONFIG3 = 0x06
    SI4703_TEST1 = 0x07
    SI4703_TEST2 = 0x08  # Reserved - if modified should be read before writing
    SI4703_BOOTCONFIG = 0x09  # Reserved - if modified should be read before writing
    SI4703_STATUSRSSI = 0x0A
    SI4703_READCHAN = 0x0B
    SI4703_RDSA = 0x0C
    SI4703_RDSB = 0x0D
    SI4703_RDSC = 0x0E
    SI4703_RDSD = 0x0F

    # Register 0x02 - POWERCFG
    SI4703_SMUTE = 15
    SI4703_DMUTE = 14
    SI4703_SKMODE = 10
    SI4703_SEEKUP = 9
    SI4703_SEEK = 8
    SI4703_ENABLE = 0

    # Register 0x03 - CHANNEL
    SI4703_TUNE = 15

    # Register 0x04 - SYSCONFIG1
    SI4703_RDSIEN = 15
    SI4703_STCIEN = 14
    SI4703_RDS = 12
    SI4703_DE = 11
    SI4703_BLNDADJ = 6
    SI4703_GPIO3 = 4
    SI4703_GPIO2 = 2
    SI4703_GPIO1 = 0

    # Register 0x05 - SYSCONFIG2
    SI4703_SEEKTH = 8
    SI4703_SPACE1 = 5
    SI4703_SPACE0 = 4
    SI4703_VOLUME_MASK = 0x000F

    # Register 0x06 - SYSCONFIG3
    SI4703_SKSNR = 4
    SI4703_SKCNT = 0

    # Register 0x07 - TEST1
    SI4703_AHIZEN = 14
    SI4703_XOSCEN = 15

    # Register 0x0A - STATUSRSSI
    SI4703_RDSR = 15
    SI4703_STC = 14
    SI4703_SFBL = 13
    SI4703_AFCRL = 12
    SI4703_RDSS = 11
    SI4703_STEREO = 8

    # Register 0x0B - READCHAN
    SI4703_BLERB = 14
    SI4703_BLERC = 12
    SI4703_BLERD = 10
    SI4703_READCHAN_MASK = 0x03FF

    # RDS Variables
    # Register RDSB
    SI4703_GROUPTYPE_OFFST = 11
    SI4703_TP_OFFST = 10
    SI4703_TA_OFFST = 4
    SI4703_MS_OFFST = 3
    SI4703_TYPE0_INDEX_MASK = 0x0003
    SI4703_TYPE2_INDEX_MASK = 0x000F

    SI4703_SEEK_DOWN = 0
    SI4703_SEEK_UP = 1

    def __init__(self, i2cAddr, resetPin, irqPIN=-1):

        GPIO.setwarnings(False)
        self.GPIO = GPIO

        self.i2CAddr = i2cAddr
        self.resetPin = resetPin
        self.irqPIN = irqPIN

        # setup the GPIO variables
        self.i2c = smbus.SMBus(1)
        self.GPIO.setmode(GPIO.BCM)
        self.GPIO.setup(self.resetPin, GPIO.OUT)
        self.GPIO.setup(0, GPIO.OUT)
        self.GPIO.setwarnings(False)

        # Global shadow copy of the si4703 registers
        self.si4703_registers = [0] * 16
        self.si4703_rds_ps = [0] * 8
        self.si4703_rds_rt = [0] * 64

        if self.irqPIN == -1:
            self.si4703UseIRQ = False
        else:
            self.si4703UseIRQ = True

    def si4703SeekUp(self):
        self.si4703Seek(self.SI4703_SEEK_UP)

    def si4703SeekDown(self):
        self.si4703Seek(self.SI4703_SEEK_DOWN)

    def si4703Seek(self, seekDirection):
        self.si4703ReadRegisters()
        # Set seek mode wrap bit
        self.si4703_registers[self.SI4703_POWERCFG] |= (1 << self.SI4703_SKMODE)  # Allow wrap
        if seekDirection == self.SI4703_SEEK_DOWN:
            # Seek down is the default upon reset
            self.si4703_registers[self.SI4703_POWERCFG] &= ~(1 << self.SI4703_SEEKUP)
        else:
            self.si4703_registers[self.SI4703_POWERCFG] |= 1 << self.SI4703_SEEKUP  # Set the bit to seek up
        self.si4703_registers[self.SI4703_POWERCFG] |= (1 << self.SI4703_SEEK)  # Start seek
        self.si4703WriteRegisters()  # Seeking will now start

        if self.si4703UseIRQ:
            self.GPIO.wait_for_edge(self.irqPIN, GPIO.FALLING, timeout=5000)
            self.si4703_registers[self.SI4703_POWERCFG] &= ~(1 << self.SI4703_SEEK)
            self.si4703WriteRegisters()
        else:
            # Poll to see if STC is set
            while True:
                self.si4703ReadRegisters()
                if (self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_STC)) != 0:
                    break  # tuning complete
            self.si4703ReadRegisters()
            self.si4703_registers[self.SI4703_POWERCFG] &= ~(
                    1 << self.SI4703_SEEK)  # Clear the tune after a tune has completed
            self.si4703WriteRegisters()

    def si4703SetChannel(self, channel):
        # newChannel = channel * 10  # e.g. 973 * 10 = 9730
        # newChannel -= 8750  # e.g. 9730 - 8750 = 980
        # newChannel /= 10  # e.g. 980 / 10 = 98
        print(channel)  # 1035
        new_Channel = channel - 875  # 1003 - 875 = 128
        print(new_Channel)  # 128
        #  new_Channel /= .1   # 128 / .1 = 1280
        #  print(new_Channel)  # 1280
        #  new_Channel /= 10   # 800 / 10 = 80
        #  print(new_Channel)  # 80


        # These steps come from AN230 page 20 rev 0.9
        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_CHANNEL] &= 0xFE00  # Clear out the channel bits
        self.si4703_registers[self.SI4703_CHANNEL] |= int(new_Channel)  # Mask in the new channel
        self.si4703_registers[self.SI4703_CHANNEL] |= (1 << self.SI4703_TUNE)  # Set the TUNE bit to start
        self.si4703WriteRegisters()

        if self.si4703UseIRQ:
            # loop waiting for STC bit to set
            self.GPIO.wait_for_edge(self.irqPIN, GPIO.FALLING, timeout=5000)
            # clear the tune flag
            self.si4703_registers[self.SI4703_CHANNEL] &= ~(1 << self.SI4703_TUNE)
            self.si4703WriteRegisters()
        else:
            # Poll to see if STC is set
            while True:
                self.si4703ReadRegisters()
                if (self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_STC)) != 0:
                    break  # tuning complete
            self.si4703ReadRegisters()
            # Clear the tune after a tune has completed
            self.si4703_registers[self.SI4703_CHANNEL] &= ~(1 << self.SI4703_TUNE)
            self.si4703WriteRegisters()

    def si4703SetVolume(self, volume):
        self.si4703ReadRegisters()
        if volume < 0:
            volume = 0
        if volume > 15:
            volume = 15
        self.si4703_registers[self.SI4703_SYSCONFIG2] &= 0xFFF0  # Clear volume bits
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= volume  # Set new volume
        self.si4703WriteRegisters()

    def si4703GetVolume(self):
        self.si4703ReadRegisters()
        return self.si4703_registers[self.SI4703_SYSCONFIG2] & self.SI4703_VOLUME_MASK

    def si4703GetChannel(self):
        self.si4703ReadRegisters()
        # Mask out everything but the lower 10 bits
        return (self.si4703_registers[self.SI4703_READCHAN] & self.SI4703_READCHAN_MASK) + 875

    def si4703SetMute(self):
        print("Mute Toggle")
        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_POWERCFG] ^= (1 << self.SI4703_DMUTE)  # toggle mute bit
        self.si4703WriteRegisters()  # Update

    def si4703DisplayStatus(self):
        self.si4703ReadRegisters()
        print("Radio Status")
        if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_RDSR):
            print("RDS Available")
            block_errors = (self.si4703_registers[self.SI4703_STATUSRSSI] & 0x0600) >> 9
            if block_errors == 0:
                print(" (No RDS errors)")
            if block_errors == 1:
                print(" (1-2 RDS errors)")
            if block_errors == 2:
                print(" (3-5 RDS errors)")
            if block_errors == 3:
                print(" (6+ RDS errors)")
        else:
            print("No RDS Data")

        if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_STC):
            print(" (Tune Complete)")
        if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_SFBL):
            print(" (Seek Fail)")
        else:
            print(" (Seek Successful!)")
        if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_AFCRL):
            print(" (AFC/Invalid Channel)")
        if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_RDSS):
            print(" (RDS Synch)")

        if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_STEREO):
            print(" (Stereo!)")
        else:
            print(" (Mono)")

        rssi = self.si4703_registers[self.SI4703_STATUSRSSI] & 0x00FF  # Mask in RSSI
        print(" (RSSI=")
        print(rssi)
        print(" of 75)")

    def si4703GetRDSData(self):
        print("Poll RDS - x to exit")
        while 1:
            self.si4703ReadRegisters()
            if self.si4703_registers[self.SI4703_STATUSRSSI] & (1 << self.SI4703_RDSR):
                print("We have RDS!")
                # byte Ah, Al, Bh, Bl, Ch, Cl, Dh, Dl;
                Ah = (self.si4703_registers[self.SI4703_RDSA] & 0xFF00) >> 8
                Al = (self.si4703_registers[self.SI4703_RDSA] & 0x00FF)

                Bh = (self.si4703_registers[self.SI4703_RDSB] & 0xFF00) >> 8
                Bl = (self.si4703_registers[self.SI4703_RDSB] & 0x00FF)

                Ch = (self.si4703_registers[self.SI4703_RDSC] & 0xFF00) >> 8
                Cl = (self.si4703_registers[self.SI4703_RDSC] & 0x00FF)

                Dh = (self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8
                Dl = (self.si4703_registers[self.SI4703_RDSD] & 0x00FF)

                print("RDS: ")
                print(Ah)
                print(Al)
                print(Bh)
                print(Bl)
                print(Ch)
                print(Cl)
                print(Dh)
                print(Dl)
                print(" !")

                time.sleep(.040)  # Wait for the RDS bit to clear
                break
            else:
                print("No RDS")
                # From AN230, using the polling method 40ms should be sufficient amount of time between checks
                time.sleep(.030)

    def si4703ClearRDSBuffers(self):
        self.si4703_rds_ps[:] = []
        self.si4703_rds_rt[:] = []

    def si4703Init(self):
        # To get the Si4703 inito 2-wire mode, SEN needs to be high and SDIO needs to be low after a reset
        # The breakout board has SEN pulled high, but also has SDIO pulled high. Therefore, after a normal power up
        # The Si4703 will be in an unknown state. RST must be controlled

        # Configure I2C and GPIO

        self.GPIO.output(0, GPIO.LOW)
        time.sleep(0.1)
        self.GPIO.output(self.resetPin, GPIO.LOW)
        time.sleep(0.1)
        self.GPIO.output(self.resetPin, GPIO.HIGH)
        time.sleep(0.1)

        self.si4703ReadRegisters()
        self.si4703_registers[self.SI4703_TEST1] = 0x8100  # Enable the oscillator, from AN230 page 12, rev 0.9
        self.si4703WriteRegisters()  # Update
        time.sleep(0.5)  # Wait for clock to settle - from AN230 page 12

        self.si4703ReadRegisters()  # Read the current register set
        self.si4703_registers[self.SI4703_POWERCFG] = 0x4001  # Enable the IC

        self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1 << self.SI4703_RDS)  # Enable RDS
        # self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1 << self.SI4703_DE)  # 50kHz Europe setup
        self.si4703_registers[self.SI4703_SYSCONFIG1] &= ~(1 << self.SI4703_DE)  # 75kHz USA setup
        self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1 << self.SI4703_GPIO2)  # Turn GPIO2 into interrupt output
        if self.si4703UseIRQ:
            # enable the si4703 IRQ pin for reading the STC flag
            self.GPIO.setup(self.irqPIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # Enable STC interrupts on GPIO2
            self.si4703_registers[self.SI4703_SYSCONFIG1] |= (1 << self.SI4703_STCIEN)

        # setting per recommended AN230 page 40
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= (0x19 << self.SI4703_SEEKTH)
        # 100kHz channel spacing for *Europe!!*
        # self.si4703_registers[self.SI4703_SYSCONFIG2] |= (1 << self.SI4703_SPACE0)
        # 200kHz channel spacing for *USA!!*
        self.si4703_registers[self.SI4703_SYSCONFIG2] &= ~(1 << self.SI4703_SPACE0)
        self.si4703_registers[self.SI4703_SYSCONFIG2] &= 0xFFF0  # Clear volume bits
        self.si4703_registers[self.SI4703_SYSCONFIG2] |= 0x0001  # Set volume to lowest

        # setting per recommended AN230 page 40
        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x04 << self.SI4703_SKSNR)
        self.si4703_registers[self.SI4703_SYSCONFIG3] |= (0x08 << self.SI4703_SKCNT)

        self.si4703WriteRegisters()  # Update

        time.sleep(.11)  # Max powerup time, from datasheet page 13

    def si4703ShutDown(self):
        self.si4703ReadRegisters()  # Read the current register set
        # Powerdown as defined in AN230 page 13 rev 0.9
        self.si4703_registers[self.SI4703_TEST1] = 0x7C04  # Power down the IC
        self.si4703_registers[self.SI4703_POWERCFG] = 0x002A  # Power down the IC
        self.si4703_registers[self.SI4703_SYSCONFIG1] = 0x0041  # Power down the IC
        self.si4703WriteRegisters()  # Update

    def si4703WriteRegisters(self):
        # A write command automatically begins with register 0x02 so no need to send a write-to address
        # First we send the 0x02 to 0x07 control registers
        # In general, we should not write to registers 0x08 and 0x09

        # only need a list that holds 0x02 - 0x07: 6 words or 12 bytes
        i2cWriteBytes = [0] * 12
        # move the shadow copy into the write buffer
        for i in range(0, 6):
            i2cWriteBytes[i * 2], i2cWriteBytes[(i * 2) + 1] = divmod(self.si4703_registers[i + 2], 0x100)

        # the "address" of the SMBUS write command is not used on the si4703 - need to use the first byte
        self.i2c.write_i2c_block_data(self.i2CAddr, i2cWriteBytes[0], i2cWriteBytes[1:11])

    def si4703ReadRegisters(self):
        # Read the entire register control set from 0x00 to 0x0F
        numRegistersToRead = 16
        i2cReadBytes = [0] * 32

        # Si4703 begins reading from register upper register of 0x0A and reads to 0x0F, then loops to 0x00.
        # SMBus requires an "address" parameter even though the 4703 doesn't need one
        # Need to send the current value of the upper byte of register 0x02 as command byte
        cmdByte = self.si4703_registers[0x02] >> 8

        i2cReadBytes = self.i2c.read_i2c_block_data(self.i2CAddr, cmdByte, 32)
        regIndex = 0x0A

        # Remember, register 0x0A comes in first, so we have to shuffle the array around a bit
        for i in range(0, 16):
            self.si4703_registers[regIndex] = (i2cReadBytes[i * 2] * 256) + i2cReadBytes[(i * 2) + 1]
            regIndex += 1
            if regIndex == 0x10:
                regIndex = 0

    def si4703ReadRDS(self):
        milli = int(time * 1000)
        endTime = milli + 15000
        completed = [False, False, False, False]
        completedCount = 0
        rds_buffer = buffer.array('u')
        while (completedCount < 4) and (milli < endTime):
            self.si4703ReadRegisters()
            if self.si4703_registers[self.STATUSRSSI] & (1 << self.SI4703_RDSR):
                # ls 2 bits of B determine the 4 letter pairs
                # once we have a full set return
                # if you get nothing after 20 readings return with empty string
                b = self.si4703_registers[self.SI4703_RDSB]
                index = b & 0x03
                if not completed[index] and b < 500:
                    completed[index] = True
                    completedCount += 1
                    Dh = (self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8
                    Dl = (self.si4703_registers[self.SI4703_RDSD] & 0x00FF)
                    rds_buffer[index * 2] = Dh
                    rds_buffer[index * 2 + 1] = Dl
                    print(self.si4703_registers[self.SI4703_RDSD])
                    print(index)
                    print(Dh)
                    print(Dl)

                time.sleep(.04)  # Wait for the RDS bit to clear

            else:
                time.sleep(
                    .03)  # From AN230, using the polling method 40ms should be sufficient amount of time between checks

            if milli >= endTime:
                rds_buffer[0] = '\0'
                return

        rds_buffer[8] = '\0'
        return rds_buffer

    def si4703_printRegisters(self):
        # Read back the registers
        self.si4703ReadRegisters()

        # Print the response array for debugging
        for x in range(16):
            print(self.si4703_registers[x])

    def isValidAsciiBasicCharacterSet(self, rdsData):
        return 32 <= rdsData <= 127

    def isValidRdsData(self):
        blockErrors = ((self.si4703_registers[self.SI4703_STATUSRSSI] & 0x0600) >> 9)  # // Mask in BLERA;

        Ch = (self.si4703_registers[self.SI4703_RDSC] & 0xFF00) >> 8
        Cl = (self.si4703_registers[self.SI4703_RDSC] & 0x00FF)

        Dh = (self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8
        Dl = (self.si4703_registers[self.SI4703_RDSD] & 0x00FF)

        return blockErrors == 0 and \
               self.isValidAsciiBasicCharacterSet(Dh) and \
               self.isValidAsciiBasicCharacterSet(Dl) and \
               self.isValidAsciiBasicCharacterSet(Ch) and \
               self.isValidAsciiBasicCharacterSet(Cl)

    def isValidStationNameData(self):
        blockErrors = ((self.si4703_registers[self.SI4703_STATUSRSSI] & 0x0600) >> 9)  # Mask in BLERA;

        Dh = (self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8
        Dl = (self.si4703_registers[self.SI4703_RDSD] & 0x00FF)

        return blockErrors == 0 and self.isValidAsciiBasicCharacterSet(Dh) and \
               self.isValidAsciiBasicCharacterSet(Dl)

    def isRadioTextData(self):
        return (self.si4703_registers[self.SI4703_RDSB] >> 11) == 4 or \
               (self.si4703_registers[self.SI4703_RDSB] >> 11) == 5

    def isStationNameData(self):
        return ((self.si4703_registers[self.SI4703_RDSB] >> 11) == 0) or \
               ((self.si4703_registers[self.SI4703_RDSB] >> 11) == 1)

    def setRadioTextData(self, pointerToRadioTextData):
        # retrieve where this data sits in the RDS message
        positionOfData = (self.si4703_registers[self.SI4703_RDSB] & 0x00FF & 0xf)

        Ch = (self.si4703_registers[self.SI4703_RDSC] & 0xFF00) >> 8
        Cl = (self.si4703_registers[self.SI4703_RDSC] & 0x00FF)

        Dh = (self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8
        Dl = (self.si4703_registers[self.SI4703_RDSD] & 0x00FF)

        characterPosition = positionOfData * 4
        pointerToRadioTextData[characterPosition] = Ch

        characterPosition = positionOfData * 4 + 1
        pointerToRadioTextData[characterPosition] = Cl

        characterPosition = positionOfData * 4 + 2
        pointerToRadioTextData[characterPosition] = Dh

        characterPosition = positionOfData * 4 + 3
        pointerToRadioTextData[characterPosition] = Dl

    def setStationNameData(self, pointerToStationNameData):
        # retrieve where this data sits in the RDS message
        positionOfData = (self.si4703_registers[self.SI4703_RDSB] & 0x00FF & 0x3)

        Dh = (self.si4703_registers[self.SI4703_RDSD] & 0xFF00) >> 8
        Dl = (self.si4703_registers[self.SI4703_RDSD] & 0x00FF)

        characterPosition = positionOfData * 2
        pointerToStationNameData[characterPosition] = Dh

        characterPosition = positionOfData * 2 + 1
        pointerToStationNameData[characterPosition] = Dl
