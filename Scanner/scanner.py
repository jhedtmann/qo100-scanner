#!/bin/python

import errno
import json
import logging
import logging.handlers
import os

from ConfigParser import SafeConfigParser
from select import select
from time import time

import requests
import serial

from statemachine import StateMachine

# constants
INI_FILENAME = 'config.ini'
LOG_FILENAME = '/tmp/scanner.log'
BUFFER_SIZE = 16
SCANNER_PIPE = '/tmp/scanner_pipe'


class Scanner(object):
    logger = None
    machine = None
    scan_list = []
    rssi_list = []
    rssi_max = 0
    current_scan_entry = 0
    has_serial_port = False
    invert_dtr = False
    last_signal_state = 0
    offset_khz = 0
    read_bouquet = True

    def __init__(self):
        """
        Initialise the state machine.
        """
        self.__configure_logging()

        self.logger.debug('Scanner() - Entered constructor.')
        self.logger.info('Scanner() - Logging initialised.')

        self.__read_configuration()
        self.__initialise()
        self.__configure_state_machine()

        self.logger.debug('Scanner() - Leaving constructor.')
        return

    def __configure_logging(self):
        # create logger
        self.logger = logging.getLogger('Scanner')
        self.logger.setLevel(logging.DEBUG)
        # create file handler which logs even debug messages
        fh = logging.handlers.RotatingFileHandler(filename=LOG_FILENAME,
                                                  mode='a',
                                                  maxBytes=5 * 1024 * 1024,
                                                  backupCount=2,
                                                  encoding=None,
                                                  delay=False
                                                  )
        fh.setLevel(logging.DEBUG)
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        return

    def __read_configuration(self):
        self.logger.debug('__read_configuration() - Entered method.')
        self.cwd = os.path.dirname(os.path.abspath(__file__))

        inifile = os.path.join(self.cwd, INI_FILENAME)
        self.parser = SafeConfigParser()
        self.parser.read(inifile)
        serial_port_name = self.parser.get('serial_port', 'name')
#        if str(serial_port_name).strip().upper() == 'NONE':
#            self.has_serial_port = False
#        else:
#            self.has_serial_port = True

        invert_dtr = self.parser.get('serial_port', 'invert_dtr')
        if str(invert_dtr).strip().upper() == 'TRUE':
            self.invert_dtr = True
        else:
            self.invert_dtr = False

        self.api_url = self.parser.get('api', 'url')
	self.logger.info(self.api_url)
        self.signal_threshold = int(self.parser.get('scanner', 'threshold'))
	self.logger.info(self.signal_threshold)
        self.hold_time = int(self.parser.get('scanner', 'hold_time'))
	self.logger.info(self.hold_time)
        self.scanlist_name = self.parser.get('scanner', 'scan_list')
	self.logger.info(self.scanlist_name)
        self.offset_khz = self.parser.get('tuner', 'offset_khz')
	self.logger.info(self.offset_khz)
        self.read_bouquet = bool(self.parser.get('tuner', 'read_bouquet'))
        self.logger.debug('__read_configuration() - Leaving method.')
        return

    def __initialise(self):
        """
        Performs the initialisation of the hardware.
        :return:
        """
        self.logger.debug('__read_configuration() - Entered method.')

        try:
            self.__read_scanlist()
            self.rssi_list = [0] * len(self.scan_list)

            self.logger.info('__initialise() - Setting up a control FIFO...')
            os.mkfifo(SCANNER_PIPE, 0777)
        except Exception as ex:
            self.logger.warn('__initialise() - FIFO exists and will e re-used: ' + str(ex))

        return

    def __read_scanlist(self):
        """
        PRIVATE
        Reads the scanlist from file and provides this as a JSON object.
        :return:
        """
        json_array = []
        if self.read_bouquet == True:
            json_array = self.__get_bouquet()

        if len(json_array) == 0:
            scanlist_file = os.path.join(self.cwd, self.scanlist_name)
            self.logger.info(scanlist_file)

            with open(scanlist_file, 'r') as scanlist:
                data = scanlist.read()

            # parse file
            json_array = json.loads(data)
            self.logger.info(data)

        for item in json_array:
            sref = item['servicereference']
            name = item['servicename']
            item_detail = {'sRef': sref, 'name': name}
            self.scan_list.append(item_detail)

        return self.scan_list

    def __configure_state_machine(self):
        self.machine = StateMachine(initial_state='off')

        self.machine.add_state('off', self.__process_off_state)
        self.machine.add_state('configuring', self.__process_configuring_state)
        self.machine.add_state('starting', self.__process_starting_state)
        self.machine.add_state('scanning', self.__process_scanning_state)
        self.machine.add_state('signal_detected', self.__process_signal_detected_state)
        self.machine.add_state('signal_lost', self.__process_signal_lost_state)
        self.machine.add_state('idling', self.__process_idling_state)
        self.machine.add_state('error', self.__process_error_state)
        self.machine.add_state('power_down', self.__process_power_down_state, True)
        return

    @staticmethod
    def __read_from_fifo():
        result = None
        try:
            client_file = os.open(SCANNER_PIPE, os.O_RDWR | os.O_NONBLOCK)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                client_file = None
            else:
                raise

        if client_file is not None:
            try:
                rlist = [client_file]
                wlist = []
                xlist = []
                rlist, wlist, xlist = select(rlist, wlist, xlist, 0.01)
                if client_file in rlist:
                    result = os.read(client_file, 1024)
            except OSError as exc:
                if exc.errno == errno.EAGAIN or exc.errno == errno.EWOULDBLOCK:
                    result = None
                else:
                    raise

            os.close(client_file)

        if result is not None:
            result = result.strip().upper()

        return result

    # State actions
    def __process_off_state(self, payload=None):
	self.logger.debug('STATE: Off')
#        while True:
#            command = self.__read_from_fifo()
#            if command == 'START':
#                new_state = 'configuring'
#                break
#
#            if command == 'OFF':
#                new_state = 'power_down'
#                break
	
	new_state = 'configuring'
        return new_state, payload

    def __process_configuring_state(self, payload=None):
	self.logger.debug('STATE: Configuring')
        while True:
            command = self.__read_from_fifo()
            if command == 'OFF':
                new_state = 'power_down'
                break

            if self.__configure_serial_port():
                new_state = 'starting'
                break
            else:
                new_state = 'error'
                break

        return new_state, payload

    def __process_starting_state(self, payload=None):
	self.logger.debug('STATE: Starting')
        while True:
            command = self.__read_from_fifo()
            if command == 'OFF':
                new_state = 'power_down'
                break

            if command == 'STOP':
                new_state = 'idling'
                break

            new_state = 'scanning'
            break

        return new_state, payload

    def __process_scanning_state(self, payload=None):
	self.logger.debug('STATE: Scanning')
        while True:
            command = self.__read_from_fifo()
            if command == 'OFF':
                new_state = 'power_down'
                break

            if command == 'PAUSE':
                new_state = 'idling'
                break

            scan_channel = self.__get_next_channel()
            self.logger.info('Scanning channel ' + scan_channel['name'])
            if self.__zap(scan_channel['sRef']) is None:
                new_state = 'scanning'
                break
            else:
                rssi = self.__poll()
                self.logger.info('RSSI: ' + str(rssi))
                if rssi > self.signal_threshold:
                    new_state = 'signal_detected'
                    payload = scan_channel
                else:
                    new_state = 'scanning'

                break

        return new_state, payload

    def __process_signal_detected_state(self, payload=None):
        self.logger.debug('STATE: Signal Detected')
        self.set_detected(True)
        while True:
            command = self.__read_from_fifo()
            if command == 'OFF':
                new_state = 'power_down'
                break

            if self.__poll() > self.signal_threshold:
                new_state = 'signal_detected'
                break
            else:
                new_state = 'signal_lost'
                break

        return new_state, payload

    def __process_signal_lost_state(self, payload=None):
        self.logger.debug('STATE: Signal Lost')
        self.set_detected(False)
        is_holding = True
        while is_holding:
            command = self.__read_from_fifo()
            if command == 'OFF':
                new_state = 'power_down'
                break

            start_time = time()
            self.diff_time = 0
            while self.diff_time < self.hold_time:
                end_time = time()
                self.diff_time = int(end_time - start_time)
                self.logger.debug('Diff.: ' + str(self.diff_time) + '  Hold: ' + str(self.hold_time))
                if self.__get_signal() > self.signal_threshold:
                    new_state = 'signal_detected'
                    return new_state, payload

            new_state = 'scanning'
            is_holding = False

        return new_state, payload

    def __process_idling_state(self, payload=None):
        self.logger.info('STATE: Idling')
        self.logger.info('Waiting for scanning to resume...')
        while True:
            command = self.__read_from_fifo()
            if command == 'OFF':
                new_state = 'power_down'
                break

            if command == 'START':
                new_state = 'scanning'
                break

        return new_state, payload

    def __process_error_state(self, payload=None):
        print('Error: ' + self.error_reason)
        if payload is not None:
            print(payload)

        return 'power_down', None

    def __process_power_down_state(self, payload=None):
        self.logger.info('Powering down the application...')
        if payload is not None:
            print(payload)

        return

    # Support methods
    def __configure_serial_port(self):
        if not self.has_serial_port:
            return True

        try:
            self.logger.info('Scanner::__configure_serial_port() - Setting up serial port...')
            self.serial_port = serial.Serial(self.parser.get('serial_port', 'name'),
                                             baudrate=int(self.parser.get('serial_port', 'baudrate')),
                                             bytesize=serial.EIGHTBITS,
                                             parity=serial.PARITY_NONE,
                                             stopbits=serial.STOPBITS_ONE,
                                             timeout=1,
                                             xonxoff=0,
                                             rtscts=0)
            result = True
        except Exception as ex:
            self.logger.error('Unable to initialise scanner. Aborting...\r\n' + str(ex))
            self.error_reason = str(ex)
            result = False

        return result

    def __get_bouquet(self):
        """
        Reads the existing channels from the currently active bouquet.
        :return:
        """
        channels = []
        if self.read_bouquet == True:
            url = self.api_url + '/getallservices'
            response = requests.get(url)
            json_result = response.json()
            services = json_result['services']
            if not services:
                return

            for service in services:
                sub_services = service['subservices']
                for sub_service in sub_services:
                    channels.append(sub_service)

        return channels

    def __zap(self, sref):
        """
        Switches the receiver to the channel described by the supplied service reference.
        :param sref: The service reference of the channel to be zapped to.
        :return: True|False
        """
        url = self.api_url + '/zap?sRef=' + sref
        response = requests.get(url)
        json_result = response.json()
        success = json_result['result']
        if success:
            return sref
        else:
            return False

    def __get_next_channel(self):
        """
        This performs the actual zapping through the channels in the scanlist.
        :return:
        """
        scan_entry = self.scan_list[self.current_scan_entry]
        count = len(self.scan_list)
        if self.current_scan_entry >= count - 1:
            self.current_scan_entry = 0
        else:
            self.current_scan_entry = self.current_scan_entry + 1

        return scan_entry

    def __poll(self):
        """
        Keeps polling the signal endpoint.
        """
        self.count = 0
        self.signal_history = []
        start_time = time()
        self.diff_time = 0
        try:
            while self.diff_time < self.hold_time:
                end_time = time()
                self.diff_time = int(end_time - start_time)
                # print('Passed: ' + str(self.passed))

                self.__get_signal()
                self.signal_history.append(self.signal)

            mean = self.__calc_mean(self.signal_history)
            return mean
        except Exception as ex:
            self.error_reason = str(ex)
            return False

    def __get_signal(self):
        """
        PRIVATE
        Sends a request for signal data to the OWIF API.
        """
        response = requests.get(self.api_url + '/tunersignal')
        json_result = response.json()
        self.signal = json_result['agc']
        self.ber = json_result['ber']
        self.snr_db = json_result['snr_db']
        self.tuner_typ = json_result['tunertype']
        if self.has_serial_port:
            self.serial_port.write(response.content)

        return self.signal

    def set_detected(self, state):
        if (state != self.last_signal_state):
            self.logger.info('Detected signal: ' + str(state))
            self.last_signal_state = state

        if not self.has_serial_port:
            return

        if state == 0 or state == 1:
            if self.invert_dtr:
                if state == 0:
                    state = 1
                elif state == 1:
                    state = 0

            self.serial_port.setDTR(state)

        return

    def __calc_mean(self, signal_history):
        """
        PRIVATE
        :param signal_history:
        :return:
        """
        mean = 0
        length = len(signal_history)
        for item in self.signal_history:
            mean = mean + item

        mean = mean / length
        return mean

    def run(self, payload=None):
        """
        Start the scanner.
        :return:
        """
        self.__get_bouquet()
        self.logger.debug('Scanner::run() - Entered method.')
        self.machine.run(payload)
        self.logger.debug('Scanner::run() - Leaving method.')
        return
