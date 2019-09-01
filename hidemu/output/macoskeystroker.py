#!/usr/bin/env python
# Copyright (c) 2019 Ross Lindsay

"""KeyStroker class for macOS (using applescript)

Simple keystroke emulation module.

"""

import time
import os

class KeyStroker:
    """Emulate key strokes required to output specified characters"""

    def __init__(self):
        pass

    def send_string(self, string):
        """Emulate typing a string"""
        cmd = "osascript -e 'tell application \"System Events\" to keystroke \"" + string + "\"'"
        os.system(cmd)

    def send_character(self, character):
        """Emulate typing a character"""
        # Press
        self._key_press(character)

    def _key_press(self, character):
        cmd = "osascript -e 'tell application \"System Events\" to keystroke \"" + character + "\"'"
        os.system(cmd)

    @staticmethod
    def _is_shifted(character):
        if character.isupper():
            return True
        if character in '~!@#$%^&*()_+{}|:"<>?':
            return True
        return False
