#!/usr/bin/env python
# Copyright (c) 2015 Sam Hall, Charles Darwin University
# See LICENSE.txt for details.
#
# acr122.py - Controls the ACR122 reader

"""ACR122 reader module

All ACR122 specific code goes here.

"""

import time
import logging
import exceptions
from base import ReaderBase
from smartcard.System import readers
from smartcard.CardRequest import CardRequest
from smartcard.Exceptions import CardConnectionException, NoCardException
from smartcard.util import toHexString, toBytes

READER_PREFIX = "ACS ACR122"

# ACR122 API Documented Commands including a short description for error handling
# Typical command format: [class, ins, p1, p2, lc] + data byte list
PICC_CMD_GET_DATA   = ["Fetch UID",   [0xFF, 0xCA, 0x00, 0x00, 0x00]]
PICC_CMD_LOAD_KEY_0 = ["Load Key 0",  [0xFF, 0x82, 0x00, 0x00, 0x06]]  # + key byte list
PICC_CMD_LOAD_KEY_1 = ["Load Key 1",  [0xFF, 0x82, 0x00, 0x01, 0x06]]  # + key byte list
PICC_CMD_MFC_AUTH   = ["Sector Auth", [0xFF, 0x86, 0x00, 0x00, 0x05, 0x01, 0x00]]  # + [block num, key type A/B, key num]
PICC_CMD_READ_BLOCK = ["Read Block",  [0xFF, 0xB0, 0x00]]  # + [block num, length]
PICC_CMD_OUTPUT_CTL = ["Output Ctl.", [0xFF, 0x00, 0x40]]  # + [LED state, lc, T1 dur., T2 dur., repetitions, buzzer]

# Example Pseudo-APDU read command (may need similar such commands for Mifare Plus)
PICC_CMD_READ_BLOCK0_DIRECT = ["Read Block Direct", [0xFF, 0x00, 0x00, 0x00, 0x05, 0xD4, 0x40, 0x01, 0x30, 0x00]]


class Reader(ReaderBase):
    """ACR122 reader class

    Built for ACR122U but may support similar USB models. This class will only ever support basic reading operations.
    """

    def __init__(self):
        ReaderBase.__init__(self)
        self.reader = Reader._find_myself()
        self.logger = logging.getLogger('hidemu')

        # Flag to ensure keys are loaded upon next connection.
        # These values are reset once keys are loaded.
        self.key_load_pending = False
        self.key_0_byte_list = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        self.key_1_byte_list = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    def connect(self, timeout=1, new_card_only=True):
        """Returns a connection if possible, otherwise returns None"""
        card_request = CardRequest(readers=[self.reader], timeout=timeout, newcardonly=new_card_only)
        card_service = card_request.waitforcard()
        try:
            card_service.connection.connect()
            self.card_authentication = None
            self.process_atr(card_service.connection.getATR())
            card_service.connection.disconnect()

            # Establish reader-centric connection
            connection = self.reader.createConnection()
            connection.connect()

            # Load keys if need be
            if self.key_load_pending: self._load_keys(connection)

            return connection
        except (CardConnectionException, NoCardException):
            return None

    def read_block(self, connection, block, length, key_a_num=None, key_b_num=None):
        """Either key A or B must be specified for Mifare Classic cards"""
        if not self.card_readable: raise exceptions.NotSupportedException("Read From Card")
        if self.card_authable:
            valid_num = [0x00, 0x01]
            assert key_a_num in valid_num or key_b_num in valid_num
            sector = block >> 2
            if sector >= 32: sector = ((sector-32) >> 2) + 32  # 4K MFC cards have 8 sectors of 16 blocks at the end
            if self.card_authentication != [sector, key_a_num, key_b_num]:
                Reader._auth_mfc(connection, block, key_a_num, key_b_num)
                self.card_authentication = [sector, key_a_num, key_b_num]
        return Reader._read_block(connection, block, length)

    def error_signal(self, duration=6):
        """If possible, blink or bleep at the user (duration in seconds)

        Intended to alert the user that there's a problem, details of the issue will be logged"""
        try:
            connection = self.reader.createConnection()
            connection.connect()
            Reader._output_control(connection, 0x50, 0x05, 0x05, duration, 0x00)
            time.sleep(duration)
        except Exception as e:
            self.logger.error('Exception while attempting to send error signals to reader: ' + type(e).__name__)
            pass

    @staticmethod
    def busy_signal(connection):
        """Orange light"""
        Reader._output_control(connection, 0x0F)  # 0x0F enables both red and green LED (makes orange)

    @staticmethod
    def ready_signal(connection):
        """Green light"""
        Reader._output_control(connection, 0x0E)  # 0x0E enables just green LED

    @staticmethod
    def _output_control(connection, led_state, t1_dur=0x00, t2_dur=0x00, repetitions=0x00, buzzer=0x00):
        try:
            Reader._transmit(connection, PICC_CMD_OUTPUT_CTL, [led_state, 0x04, t1_dur, t2_dur, repetitions, buzzer])
        except exceptions.UnexpectedErrorCodeException, args:
            # Current LED State returned via sw2 which _transmit does not expect
            sw1 = args[3]
            if sw1 == 0x90: pass
            else: raise

    def set_keys(self, key_0=None, key_1=None):
        """Specify reader keys 0 and 1 as 12 character hex strings (not to be confused with sector keys A and B)

        These keys will be used to access blocks, at that time either key 1 or 2 can be used as key A and/or B.

        Omitting a key will revert it to the default FF key"""
        if key_0 is None: key_0 = "FFFFFFFFFFFF"
        if key_1 is None: key_1 = "FFFFFFFFFFFF"
        assert len(key_0) == 12 and len(key_1) == 12
        assert int(key_0, 16) and int(key_1, 16)  # throws ValueError if not a hex string

        # TODO: Look for more secure way of loading keys
        # using command line args which then go on to create immutable hex strings seems less than ideal

        # Set a flag to load the keys as soon as the next card arrives
        self.key_0_byte_list = toBytes(key_0)
        self.key_1_byte_list = toBytes(key_1)
        self.key_load_pending = True

    def _load_keys(self, connection):
        """Load keys into the reader"""
        assert len(self.key_0_byte_list) == 6 and len(self.key_1_byte_list) == 6
        Reader._transmit(connection, PICC_CMD_LOAD_KEY_0, self.key_0_byte_list)
        Reader._transmit(connection, PICC_CMD_LOAD_KEY_1, self.key_1_byte_list)

        for i in range(0, 6):  # Wipe the stored key
            self.key_0_byte_list[i] = 0xFF
            self.key_1_byte_list[i] = 0xFF
        self.key_load_pending = False

    @staticmethod
    def get_serial_number(connection):
        """Returns card serial number in bytes"""
        return Reader._transmit(connection, PICC_CMD_GET_DATA)

    @staticmethod
    def _find_myself():
        """Iterate through the list of readers looking for the first one with matching prefix"""
        for r in readers():
            if READER_PREFIX in r.name and r.name.index(READER_PREFIX) == 0:
                return r
        raise exceptions.ReaderNotFoundException

    @staticmethod
    def _transmit(connection, command, command_vars=None):
        """Returns: data as a byte list"""
        if command_vars is None: command_vars = []
        command_desc = command[0]
        full_command = command[1] + command_vars
        sw = [0, 0]
        try:
            data, sw[0], sw[1] = connection.transmit(full_command)
        except(AttributeError, IndexError):
            # Connection lost
            raise exceptions.ConnectionLostException
        response_code = toHexString(sw)
        if response_code == "63 00":
            raise exceptions.FailedException(command_desc)
        elif response_code == "6A 81":
            raise exceptions.NotSupportedException(command_desc)
        elif response_code != "90 00":
            raise exceptions.UnexpectedErrorCodeException(response_code, command_desc, sw[0], sw[1])
        return data

    @staticmethod
    def _read_block(connection, block, length):
        assert 0x00 <= block <= 0xff
        assert 0x00 <= length <= 0xff

        data = Reader._transmit(connection, PICC_CMD_READ_BLOCK, [block, length])
        # data = Reader._transmit(connection, PICC_CMD_READ_BLOCK0_DIRECT)
        return data

    @staticmethod
    def _auth_mfc(connection, block, key_a=None, key_b=None):
        """Either key A or B must be specified"""
        reader_keys = [0x00, 0x01]
        assert key_a in reader_keys or key_b in reader_keys
        assert 0x00 <= block <= 0xff

        if key_a is not None:
            Reader._transmit(connection, PICC_CMD_MFC_AUTH, [block, 0x60, key_a])
        if key_b is not None:
            Reader._transmit(connection, PICC_CMD_MFC_AUTH, [block, 0x61, key_b])
