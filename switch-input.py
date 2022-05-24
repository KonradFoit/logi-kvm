#!/usr/bin/env python
"""Provides switching Logitech Unifying devices channels and VCP compliant monitors input switch
as a reaction to Logitech Easy Switch keys events

Notes:
    Unifying channels indexes starts at 0
    Unifying receiver slots indexes starts at 1
    Any Unifying Hardware should be compatible. In order to check what message has to be sent to the device to
    make it switch channel user has to check number of feature called "CHANGE HOST". This can be checked using
    software Solaar by listing devices via command 'solaar show'. This number has to be byte number 2 in
    switch_message in UnifyingDevice class. Byte number 3 in this message is, as for authors current knowledge,
    a magic byte and has to be found by try and error.
    Display number and input name has to be found by try and error.

    Configuration is created in function populate_devices
"""


import argparse
import sys
import logging
from logging.handlers import RotatingFileHandler
import monitorcontrol
import hid

__author__ = "Konrad Foit"
__copyright__ = "Copyright 2022, Konrad Foit"
__credits__ = ["https://github.com/Logitech/logi_craft_sdk/issues/28"]

__license__ = "MIT"
__maintainer__ = "Konrad Foit"
__status__ = "Development"


UNIFYING_RECEIVER_VID = 0x046D
UNIFYING_RECEIVER_PID = 0xC52B
UNIFYING_RECEIVER_LISTEN_USAGE_PAGE = 0xFF00
UNIFYING_RECEIVER_SEND_USAGE_PAGE = 0xFF00
UNIFYING_RECEIVER_LISTEN_USAGE = 0x0002
UNIFYING_RECEIVER_SEND_USAGE = 0x0001

listen_device_path = ""
send_device_path = ""


def unifying_listen():
    h = hid.device()
    h.open_path(listen_device_path)
    h.set_nonblocking(0)
    data = h.read(11)
    h.close()
    return data


def unifying_write(data):
    h = hid.device()
    h.open_path(send_device_path)
    h.set_nonblocking(0)
    h.write(data)
    h.close()


def usb_discover():
    for dev in hid.enumerate(UNIFYING_RECEIVER_VID, UNIFYING_RECEIVER_PID):
        if dev['usage'] == UNIFYING_RECEIVER_LISTEN_USAGE and dev['usage_page'] == UNIFYING_RECEIVER_LISTEN_USAGE_PAGE:
            global listen_device_path
            listen_device_path = dev['path']
        elif dev['usage'] == UNIFYING_RECEIVER_SEND_USAGE and dev['usage_page'] == UNIFYING_RECEIVER_SEND_USAGE_PAGE:
            global send_device_path
            send_device_path = dev['path']


class UnifyingDevice:
    def __init__(self, dev_type, slot_id, self_channel):
        self.slot_id = slot_id
        self.dev_type = dev_type
        if dev_type.lower() == 'MX Keys'.lower():
            # byte 0 0x11 is header
            # byte 1 contains index of a slot on which device is paired in unifying receiver
            # byte 2 is always 0x08
            # byte 3 is always 0x20
            # byte 4 is always 0x00
            # byte 5 contains key number. For MX Keys easy switch keys are 0xD1, 0xD2, 0xD3
            # byte 6 is key state 0x01 is pressed, 0x00 is released
            self.switch_detect_message = [0x11, slot_id, 0x08, 0x20, 0x00, 0xFF, 0x01]
            self.easy_switch_keys = [0xD1, 0xD2, 0xD3]
            # byte 4 (0xFF) is a placeholder for target channel number
            self.switch_message = [0x10, slot_id, 0x09, 0x1e, 0xFF, 0x00, 0x00]
            self.max_channels = 3
        elif dev_type.lower() == 'MX Ergo'.lower():
            # MX Ergo doesn't provide event on channel switch button
            self.switch_detect_message = []
            self.easy_switch_keys = []
            # byte 4 (0xFF) is a placeholder for target channel number
            self.switch_message = [0x10, slot_id, 0x15, 0x1b, 0xFF, 0x00, 0x00]
            self.max_channels = 2
        elif dev_type.lower() == 'MX Master 3'.lower():
            # byte 6 is placeholder for key value
            # To be verified, probably wrong
            self.switch_detect_message = [0x11, slot_id, 0x08, 0x20, 0x00, 0xFF, 0x01]
            # To be verified, probably wrong
            self.easy_switch_keys = [0xD1, 0xD2, 0xD3]
            # To be verified
            # byte 2 is feature number for "CHANGE HOST". It can be checked in solaar by listing devices (solaar show)
            # byte 3 is magic number, for now, you simply have to check values until you hit correct one
            # byte 4 (0xFF) is a placeholder for target channel number
            self.switch_message = [0x10, slot_id, 0x0A, 0x11, 0xFF, 0x00, 0x00]
            self.max_channels = 3
        else:
            raise ValueError("Invalid Unifying device type")

    def decode_target_channel_number(self, input_bytes):
        # Initial value indicating fault
        target_channel = -1
        if len(self.switch_detect_message) <= len(input_bytes):
            if (self.dev_type.lower() == 'MX Keys'.lower()) or (self.dev_type.lower() == 'MX Master 3'.lower()):
                # Compare first 5 bytes (0 - 4) and byte 6. Byte 5 contains information about new channel.
                if (input_bytes[:4] == self.switch_detect_message[:4]) and \
                        (input_bytes[6] == self.switch_detect_message[6]):
                    for esk in self.easy_switch_keys:
                        if esk == input_bytes[5]:
                            target_channel = self.easy_switch_keys.index(esk)
            elif self.dev_type.lower() == 'MX Ergo'.lower():
                # MX Ergo doesn't send information about switch button event
                target_channel = -2
            else:
                raise NotImplementedError
        return target_channel

    def switch_channel(self, channel_number):
        self.switch_message[4] = channel_number
        logging.debug("Switching Unifying device \'%s\' at slot %d to channel %d" % (self.dev_type, self.slot_id,
                      channel_number))
        unifying_write(self.switch_message)


class VirtualMonitor:
    def __init__(self, unifying_channel, monitor_id, input_value, vcp_message_number=60):
        self.unifying_channel = unifying_channel
        self.monitor_id = monitor_id
        self.input_value = input_value
        self.vcp_message_number = vcp_message_number


class Monitor:
    def __init__(self, virtual_monitors):
        self.virtual_monitors = []
        self.virtual_monitors = virtual_monitors

    def switch_input(self, self_channel, channel_number):
        for vm in self.virtual_monitors:
            if vm.unifying_channel == self_channel:
                target_input = vm.input_value
                for tvm in self.virtual_monitors:
                    if tvm.unifying_channel == channel_number:
                        target_input = tvm.input_value

                monitor = monitorcontrol.get_monitors()[vm.monitor_id]
                with monitor:
                    old_input = monitor.get_input_source()
                    if old_input != target_input:
                        logging.debug("Switch monitor %d from input %s to input %s" % (vm.monitor_id,
                                                                                       old_input,
                                                                                       target_input))
                        monitor.set_input_source(target_input)
                    else:
                        logging.debug("Display %d monitor % is already set to input %d" % (vm.display_id,
                                                                                           vm.monitor_id, target_input))


class Device:
    def __init__(self, unifying_channel, unifying_devices, monitors):
        self.unifying_channel = unifying_channel
        self.unifying_devices = unifying_devices
        self.monitors = monitors

    def switch_channel(self, channel_number, detection_slot):
        for monitor in self.monitors:
            monitor.switch_input(self.unifying_channel, channel_number)

        for unifying_device in self.unifying_devices:
            if unifying_device.slot_id != detection_slot:
                unifying_device.switch_channel(channel_number)
            else:
                logging.debug("Skipping Unifying device \'%s\' at slot %d as the source of switch" %
                              (unifying_device.dev_type, unifying_device.slot_id))


def populate_devices(devices_list, self_channel):
    # Unifying receiver slots are numbered from 1
    mx_ergo = UnifyingDevice(dev_type='MX Ergo', slot_id=2, self_channel=self_channel)
    mx_keys = UnifyingDevice(dev_type='MX Keys', slot_id=1, self_channel=self_channel)
    main_monitor_pc = VirtualMonitor(unifying_channel=0, monitor_id=2, input_value="HDMI2")
    main_monitor_laptop = VirtualMonitor(unifying_channel=1, monitor_id=1, input_value="HDMI1")
    main_monitor = Monitor(virtual_monitors=[main_monitor_pc, main_monitor_laptop])
    # Unifying channels are numbered from 0
    devices_list.append(Device(unifying_channel=0, unifying_devices=[mx_keys, mx_ergo], monitors=[main_monitor]))
    devices_list.append(Device(unifying_channel=1, unifying_devices=[mx_keys, mx_ergo], monitors=[main_monitor]))


def main_loop(self_channel):
    devices = []
    populate_devices(devices, self_channel)
    while True:
        read_bytes = unifying_listen()
        for device in devices:
            if device.unifying_channel == self_channel:
                for unifying_device in device.unifying_devices:
                    channel_number = unifying_device.decode_target_channel_number(read_bytes)
                    if channel_number >= 0:
                        if channel_number != self_channel:
                            logging.info("Switch to channel " + str(channel_number) + " from device \'" +
                                         unifying_device.dev_type + "\' at slot " + str(unifying_device.slot_id))
                            device.switch_channel(channel_number, unifying_device.slot_id)


if __name__ == '__main__':
    logFormatter = logging.Formatter("%(asctime)s,%(msecs)03d %(levelname)s %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    logFile = "log.log"
    fileHandler = RotatingFileHandler(logFile, mode='a', maxBytes=16*1024*1024, backupCount=2,
                                      encoding=None, delay=False)
    fileHandler.setFormatter(logFormatter)
    fileHandler.setLevel(logging.DEBUG)

    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setFormatter(logFormatter)

    app_log = logging.getLogger('root')
    app_log.setLevel(logging.DEBUG)

    app_log.addHandler(fileHandler)
    app_log.addHandler(consoleHandler)

    parser = argparse.ArgumentParser(description="Logitech unifying and HDMI monitor input switch")
    parser.add_argument('channel', metavar='Ch', type=int,
                        help='Logitech Unifying self channel (this computer), numbered from  0')
    args = vars(parser.parse_args())

    logging.info("Discovering USB devices")
    usb_discover()

    logging.info("Self unifying channel is " + str(args['channel']))
    main_loop(args['channel'])
