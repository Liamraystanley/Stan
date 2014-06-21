#!/usr/bin/env python
"""
    Stan - Minecraft Classic Server Bot
    Stan Copyright Liam Stanley (2014)
    License: https://github.com/Liamraystanley/Stan/blob/master/LICENSE
    NOTICE: ALL COPYRIGHT NOTICES MUST BE KEPT
    FAILURE TO DO SO IS BREAKING LICENSE TERMS
"""

import socket
import struct
import hashlib
import time
import thread
import threading
import os
import sys
import re

username = "Swagger"
heartbeat_file = '/root/classic/heartbeatdata.txt'
ip = "2.liamstanley.io"
port = 25566


class Bot(object):

    def __init__(self, username, fn, ip, port):
        self.username = username
        self.fn = fn
        self.ip = ip
        self.port = port
        self.prefix = '!'
        self.triggers = [
            {
                'on': 'players', 'args': [], 'command': True,
                'event': 'irc', 'input': 'message',
                'response': '/players'
            },
            {
                'on': r'(?i)herpderptrains', 'args': [], 'command': False,
                'event': 'irc', 'input': 'message',
                'response': '{name}! I love hugging trains too!'
            },
            {
                'on': 'test', 'args': [], 'command': True,
                'event': 'irc', 'input': 'message',
                'response': '/info Liam'
            },
        ]
        self.base_triggers = [
            {
                'name': 'chat', 'args': ['name', 'message'],
                'r': r'^([a-zA-Z0-9_]{2,16})\: (.*?)$'
            },
            {
                'name': 'join', 'args': ['name'],
                'r': r'^([a-zA-Z0-9_]{2,16}) connected.*?joined [a-zA-Z0-9_-]{1,20}$'
            },
            {
                'name': 'irc', 'args': ['name', 'message'],
                'r': r'^\(IRC\) (.*?)\: (.*?)$'
            },
            {
                'name': 'players', 'args': ['count', 'list'],
                'r': r'^There are ([0-9]{1,3}) players online: (.*?)$'
            }
        ]
        self.FORMAT_LENGTHS = {"b": 1, "a": 1024, "s": 64, "h": 2, "i": 4}
        # Allowed to be parsed. All others are ignored...
        self.passing = [0, 7, 13, 14]
        self.TYPE_FORMATS = {
            0: "bssb",     # TYPE_INITIAL
            1: "",         # TYPE_KEEPALIVE
            2: "",         # TYPE_PRECHUNK
            3: "hab",      # TYPE_CHUNK
            4: "hhh",      # TYPE_LEVELSIZE
            5: "hhhbb",    # TYPE_BLOCKCHANGE
            6: "hhhb",     # TYPE_BLOCKSET
            7: "bshhhbb",  # TYPE_SPAWNPOINT
            8: "bhhhbb",   # TYPE_PLAYERPOS
            9: "bbbbbb",   # TYPE_NINE
            10: "bbbb",    # TYPE_TEN
            11: "bbb",     # TYPE_PLAYERDIR
            12: "b",       # TYPE_PLAYERLEAVE
            13: "bs",      # TYPE_MESSAGE
            14: "s"        # TYPE_ERROR
        }
        self.send_buffer, self.recv_buffer = [], []

    def connect(self):
        """ Make the inital connection the server, thread the socket receive/send to generate buffers """
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((str(self.ip), int(self.port)))

        # now for the packet
        # note that the String type is specified as having a length of 64, we'll pad that
        # Null packets are 0
        with open(self.fn, 'r') as f:
            self.hash = f.read().split('\n')[0]
        self.hash = str(hashlib.md5(self.hash + username).hexdigest())
        self.s.sendall('%c%c%-64s%-64s%c' % (0, 7, self.username, self.hash, 0))
        try:
            thread.start_new_thread(self.sendData, ())
            thread.start_new_thread(self.line, ())
            self.receiveData()
        except:
            print('\n\nTerminating the bot...')
        os._exit(1)

    def packString(self, string, length=64, packWith=" "):
        """ Makes strings pack-able. Make sure they're safe. """
        return string + (packWith * (length - len(string)))

    def decode(self, format, data):
        """ Decode packets received from the server Make sure each byte is parsed in the correct format """
        for char in format:
            if char == "b":
                yield struct.unpack("!B", data[0])[0]
            elif char == "a":
                yield data[:1024]
            elif char == "s":
                yield data[:64].strip()
            elif char == "h":
                yield struct.unpack("!h", data[:2])[0]
            elif char == "i":
                yield struct.unpack("!i", data[:4])[0]
            data = data[self.FORMAT_LENGTHS[char]:]

    def get_hash(self, fn):
        """ Read the salt from the externaldata.txt (or likewise for your server) """
        with open(fn, 'r') as f:
            data = f.read().split('\n')[0]
        return str(hashlib.md5(data + username).hexdigest())

    def removeColors(self, msg):
        """ Strip color-codes from msg """
        tmp = re.sub(re.compile(r'\&.?'), '', msg)
        return tmp

    def sendData(self):
        """ Threaded function that reads data from the buffer """
        while True:
            if not self.send_buffer:
                continue
            time.sleep(0.1)
            current_time = float(time.time())
            diff = current_time - self.send_buffer[0]['time']
            if not self.send_buffer[0]['complete'] and diff < 1:
                continue
            for i in range(len(self.send_buffer)):
                msg = self.send_buffer[i]['raw']
                msg = self.removeColors(msg)  # Remove colors
                for trigger in self.base_triggers:
                    tmp = re.match(re.compile(trigger['r']), msg)
                    if tmp:
                        _args = list(tmp.groups())
                        if len(_args) != len(trigger['args']):
                            continue
                        args = {}
                        for i in range(len(trigger['args'])):
                            args[trigger['args'][i]] = _args[i]
                        if 'name' in args:
                            if args['name'] == self.username or args['name'] == 'Reminder':
                                continue
                        trigger = trigger['name']

                        for user_trigger in self.triggers:
                            if user_trigger['event'] != trigger:
                                continue
                            if user_trigger['command']:
                                r_trigger = r'(?i)^\%s%s(?: +(.*))?$' % (self.prefix, user_trigger['on'])
                                ut_args = ['args']
                            else:
                                r_trigger = user_trigger['on']
                                ut_args = user_trigger['args']
                            tmp = re.match(re.compile(r_trigger), args[user_trigger['input']])
                            if not tmp:
                                continue
                            user_trigger_args = list(tmp.groups())
                            if len(user_trigger_args) != len(ut_args):
                                continue
                            trigger_args = {}
                            for i in range(len(user_trigger['args'])):
                                trigger_args[user_trigger['args'][i]] = user_trigger_args[i]
                            self.sendMessage(user_trigger['response'], args, trigger_args)

                        # Triggering here...
                        if trigger == 'chat':
                            output(args['name'], args['message'])
                        if trigger == 'join':
                            output(args['name'], 'joined the server.')
                            self.sendMessage('Hi {name}! Welcome to the server!', args)
                        if trigger == 'irc':
                            output('(IRC) ' + args['name'], args['message'])
                        if trigger == 'players':
                            print(self.send_buffer)
                            self.sendMessage('{count} player(s): {list}', args)
            self.send_buffer = []

    def sendMessage(self, message, args=False, targs=False):
        """ Function that packs and sends messages via the socket to the server """
        if args:
            if targs:
                for key, value in targs.iteritems():
                    args[key] = value
            message = message.format(**args)
        self.s.sendall('%c%c%-64s' % (chr(13), chr(0xFF), self.packString(message)))

    def receiveData(self):
        """ Loops through the socket.recv and sends the data to the line parser """
        while True:
            buffer = self.s.recv(2048)
            self.recv_buffer.append(buffer)

    def line(self):
        """ Funtion that checks consistancy between packets, and ensures we're buffering the right packets """
        while True:
            time.sleep(0.1)
            if not self.recv_buffer:
                continue
            for buffer in self.recv_buffer:
                #if not buffer:
                #    continue
                type = ord(buffer[0])
                if type not in self.passing or not type in self.TYPE_FORMATS:
                    continue
                format = self.TYPE_FORMATS[type]
                if len(buffer)-1 < len(format):
                    continue
                try:
                    parts = list(self.decode(format, buffer[1:]))
                except:
                    continue

                curr_time = float(time.time())
                if type == 13:  # Assume message
                    if parts[1].startswith('>'):
                        self.send_buffer[0]['raw'] = self.send_buffer[0]['raw'] + ' ' + parts[1].split('>', 1)[1].strip()
                        self.send_buffer[0]['time'] = curr_time
                    elif len(parts[1].strip()) < 58:
                        self.send_buffer.append({'id': type, 'raw': parts[1], 'complete': True, 'time': curr_time})
                    else:
                        self.send_buffer.append({'id': type, 'raw': parts[1], 'complete': False, 'time': curr_time})
                elif type == 0:
                    msg = self.removeColors(parts[1])
                    output('SERVER', msg)
                elif type == 14:
                    print(parts)
                print(' | '.join([str(type), str(parts)]))
            self.recv_buffer = []


def output(*args):
    print('[{}] {}'.format(*args))

if __name__ == "__main__":
    b = Bot(username, heartbeat_file, ip, port)
    b.connect()
