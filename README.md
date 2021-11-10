# NFC HID Emulate
Human Interface Device emulator for NFC readers. The niche purpose being to provide similar functionality to that of a standard USB HID Magnetic Stripe Reader (MSR). Defaults to simply returning the chip serial number in a similar format to that of a MSR.

Testing performed initially on the ACR122U model NFC reader, but other ACR brand USB models should work with some minor modifications to the reader package.

Reader support recently added for SDI011 and Omnikey 5x21 CL (tested specifically with Omnikey 5021 CL model). Only tested these readers on Windows.

Designed to run as a service in the background (or more accurately, a user daemon - since it requires the current user desktop session to function). The ideal time to start the program is on login. To avoid conflicts, the application will only attempt to load once. You may have problems getting it to work after switching users unless the first user logs out completely.

There are some command line args, you can bring up all currently available options with the "-h" switch.

## Platforms
Runs on Python 3.8.5 and 3.9.5

### Windows
Tested on Windows 10 64bit

Maintain same architecture as OS (reader drivers and python stuff)

Requires:

* pyscard 1.7
* No drivers required
* Smart Card service required (should start as soon as the reader installs via Plug and Play)

### Linux
Tested on Ubuntu 20.04

Requires:

* ACS Unified Linux drivers
* pcscd
* libpcsclite-dev
* python-xlib
* swig (to build pyscard from source)
* pyscard (build latest from source)

### OSX
Tested on macOS Catalina 10.15.

Requires:

* ACS Unified Installer OSX drivers
* pyobjc
* swig (to build pyscard from source)
* pyscard (build latest from source)
