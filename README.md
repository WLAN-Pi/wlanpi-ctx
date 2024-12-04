![versions](docs/images/ctx-pybadge-w-logo.svg) ![coverage-badge](coverage.svg) [![packagecloud-badge](https://img.shields.io/badge/deb-packagecloud.io-844fec.svg)](https://packagecloud.io/)

# wlanpi-ctx

ctx is a Wi-Fi continuous transmitter testing tool built for the [WLAN Pi](https://github.com/WLAN-Pi/).

## Why?

Just for continuously transmitting random data.

## Installation

ctx is not yet included in the [WLAN Pi](https://github.com/WLAN-Pi/) image as a Debian package, but if you want to install it manually, here is what you need:

General requirements:

- adapter (and driver) which supports both monitor mode and packet injection
  - mt76x2u, mt7921u (a8000), mt7921e (rz608/mt7921k, rz616/mt7922m), and iwlwifi (ax200, ax210, be200) are tested regularly (everything else is experimental and not officially supported).
  - removed from the recommended list are rtl88XXau adapters (certain comfast adapters for example), but they should still work. with that said, don't open a bug report here for a rtl88XXau card.
- elevated permissions

Package requirements:

- Python version 3.9 or higher
- `iw`, `iproute2`, `pciutils`, `usbutils`, `kmod`, `wpa_cli`, and `wpasupplicant` tools installed on the host. most distributions already come with these.

### Upgrading WLAN Pi OS v3 (C4, M4, Pro) installs.

Got your hands on a WLAN Pi C4, M4, or Pro? We build and deploy a Debian package for `wlanpi-ctx` to our package archive. Get the latest version by running `sudo apt update` and `sudo apt install wlanpi-ctx`.

### Upgrading existing WLAN Pi OS v2 (NEO2) installs via pipx:

Are you reading this and have a NEO2 WLAN Pi? You can upgrade your existing ctx install, but there are some manual things you need to do first. Check out the [upgrading with pipx](UPGRADING_WITH_PIPX.md) instructions.

### Don't have a WLAN Pi? Installing via pipx:

Don't have a WLAN Pi? Have a Linux host handy? Try the [installing wlanpi-ctx using pipx](INSTALLING_WITH_PIPX.md) instructions.

# Usage from the CLI

You can start ctx directly from the command line like this:

```
sudo ctx
```

Stop with `CTRL + C`.

Usage:

```
usage: ctx [-h] [-c CHANNEL | -f FREQUENCY] [-i INTERFACE] [--tx_interval INTERVAL] [--tx_payload_max MAX] [--tx_payload_min MIN] [--config FILE] [--debug] [--noprep] [--list_interfaces]
                   [--version]

wlanpi-ctx is a continuous random data frame transmitter.

optional arguments:
  -h, --help            show this help message and exit
  -c CHANNEL            set the channel to broadcast on
  -f FREQUENCY          set the frequency to broadcast on
  -i INTERFACE          set network interface for ctx
  --tx_interval INTERVAL
                        customize the Tx interval for QoS data frames (default: 0.001)
  --tx_payload_max MAX  customize the Tx payload maximum (default: 512)
  --tx_payload_min MIN  customize the Tx payload minimum (default: 64)
  --config FILE         customize path for configuration file (default: /etc/wlanpi-ctx/config.ini)
  --debug               enable debug logging output
  --noprep              disable interface preperation (default: False)
  --list_interfaces     print out a list of interfaces with an 80211 stack
  --version, -V         show program's version number and exit
```

## Usage Examples

We require elevated permissions to put the interface in monitor mode and to open raw native sockets for frame injection. Starting and stopping ctx from the WLAN Pi's Front Panel Menu System (FPMS) will handle this for you automatically. Otherwise, when run from CLI elevated permissions are required:

```
# Default parameters listed in start up message
$ sudo ctx

2024-12-03 21:42:49,740 [WARNING] setup_config: can not find config at /etc/wlanpi-ctx/config.ini

#/~>
Starting a fake AP using wlan0mon (a0:02:a5:xx:xx:xx) on channel 36 (5180)
 - Transmitting QoS Data frames to 02:00:00:31:41:59 every 0.001
 - Payload is os.urandom(length) where length is a random integer between 64 and 512
#/~>

2024-12-03 21:42:54,109 [INFO] fakeap.py: starting QoS data frame transmissions
```

Don't want to use the default channel? You can change it with the `-c` option:

```
# Transmit data frames on channel 48
$ sudo ctx -c 48
```

```
# Change the tx interval and tx payload min and max values
$ sudo ctx --tx_payload_min 128 --tx_payload_max 128 --tx_interval 0.1

2024-12-03 21:50:47,661 [WARNING] setup_config: can not find config at /etc/wlanpi-ctx/config.ini

#/~>
Starting a fake AP using wlan0mon (a0:02:a5:ce:78:ef) on channel 36 (5180)
 - Transmitting QoS Data frames to 02:00:00:31:41:59 every 0.1
 - Payload is os.urandom(length) where length is a random integer between 128 and 128
#/~>

2024-12-03 21:50:52,149 [INFO] fakeap.py: starting QoS data frame transmissions
```

Something not working? Use `--debug` to get more logs printed to the shell.

```
# increase output to screen for debugging
$ sudo ctx --debug
```

## Feature: overriding defaults with configuration file support

To change the default operation of the script (without passing in CLI args), on the WLAN Pi, a configuration file can be found at `/etc/wlanpi-ctx/config.ini`. 

This can be used as a way to modify settings loaded at runtime such as channel, interface, and payload min/max values. 

# Contributing

Want to contribute? Thanks! Please take a few moments to [read this](CONTRIBUTING.md).

# Discussions and Issues

Please use GitHub discussions for dialogue around features and ideas that do not exist. Create issues for problems found running ctx.