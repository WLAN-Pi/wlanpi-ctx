# -* coding: utf-8 -*-
#
# ctx : a Wi-Fi client capability analyzer tool
# Copyright : (c) 2024 Josh Schmelzle
# License : BSD-3-Clause
# Maintainer : josh@joshschmelzle.com

"""
ctx.helpers
~~~~~~~~~~~~~~~~

provides init functions that are used to help setup the app.
"""

# standard library imports
import argparse
import configparser
import inspect
import json
import logging
import logging.config
import os
import shutil
import signal
import subprocess
import sys
from base64 import b64encode
from dataclasses import dataclass
from typing import Any, Dict


__tools = [
    "tcpdump",
    "iw",
    "ip",
    "ethtool",
    "lspci",
    "lsusb",
    "modprobe",
    "modinfo",
    "wpa_cli",
]

# are the required tools installed?
for tool in __tools:
    if shutil.which(tool) is None:
        print(f"It looks like you do not have {tool} installed.")
        print("Please install using your distro's package manager.")
        sys.exit(signal.SIGABRT)


# app imports
from .__init__ import __version__
from .constants import CHANNELS, CONFIG_FILE

FILES_PATH = "/var/www/html/ctx"


def setup_logger(args) -> None:
    """Configure and set logging levels"""
    logging_level = logging.INFO
    if args.debug:
        logging_level = logging.DEBUG

    default_logging = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"}
        },
        "handlers": {
            "default": {
                "level": logging_level,
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {"": {"handlers": ["default"], "level": logging_level}},
    }
    logging.config.dictConfig(default_logging)


def channel(value: str) -> int:
    """Check if channel is valid"""
    ch = int(value)
    if any(ch in band for band in CHANNELS.values()):
        return ch
    raise argparse.ArgumentTypeError(f"{ch} is not a valid channel")

def interval(value: str) -> float:
    """Check if the given string can be converted to a float."""
    interval = float(value)
    try:
        return interval
    except ValueError:
        raise argparse.ArgumentTypeError(f"{interval} is not a valid interval")

def payload_size(value: str) -> int:
    """Check if the value is an integer and between 1 and 4096."""
    size = int(value)
    if isinstance(size, int) and 1 <= size <= 4096:
        return int(size)
    raise argparse.ArgumentTypeError(f"{size} is not an integer between 1 and 4096")

def frequency(freq: str) -> int:
    """Check if the provided frequency is valid"""
    try:
        # make sure freq is an int
        freq = int(freq)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{freq} is not a number")

    freq_ranges = [(2412, 2484), (5180, 5905), (5955, 7115)]

    for band in freq_ranges:
        if band[0] <= freq <= band[1]:
            return freq

    raise argparse.ArgumentTypeError(f"{freq} not found in these frequency ranges: {freq_ranges}")


def setup_parser() -> argparse.ArgumentParser:
    """Set default values and handle arg parser"""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="wlanpi-ctx is a continuous random data frame transmitter.",
    )
    parser.add_argument(
        "--pytest",
        dest="pytest",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )
    frequency_group = parser.add_mutually_exclusive_group()
    frequency_group.add_argument(
        "-c",
        dest="channel",
        type=channel,
        help="set the channel to broadcast on",
    )
    frequency_group.add_argument(
        "-f",
        dest="frequency",
        type=frequency,
        help="set the frequency to broadcast on",
    )
    parser.add_argument(
        "-i",
        dest="interface",
        help="set network interface for ctx",
    )
    parser.add_argument(
        "--tx_interval",
        type=interval,
        metavar="INTERVAL",
        default="0.001",
        help="customize the Tx interval for QoS data frames (default: %(default) seconds)",
    )
    parser.add_argument(
        "--tx_payload_max",
        type=payload_size,
        metavar="MAX",
        default="512",
        help="customize the Tx payload maximum (default: %(default)s)",
    )
    parser.add_argument(
        "--tx_payload_min",
        type=payload_size,
        metavar="MIN",
        default="64",
        help="customize the Tx payload minimum (default: %(default)s)",
    )
    parser.add_argument(
        "--config",
        type=str,
        metavar="FILE",
        default=CONFIG_FILE,
        help="customize path for configuration file (default: %(default)s)",
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="enable debug logging output",
    )
    parser.add_argument(
        "--noprep",
        dest="no_interface_prep",
        action="store_true",
        default=False,
        help="disable interface preperation (default: %(default)s)",
    )
    parser.add_argument(
        "--list_interfaces",
        dest="list_interfaces",
        action="store_true",
        default=False,
        help="print out a list of interfaces with an 80211 stack",
    )
    parser.add_argument("--version", "-V", action="version", version=f"{__version__}")
    return parser


@dataclass
class NetworkInterface:
    """Class for our Network Interface object"""

    ifname: str = ""
    operstate: str = ""
    mac: str = ""


def get_data_from_iproute2(intf) -> NetworkInterface:
    """Get and parse output from iproute2 for a given interface"""
    # Get json output from `ip` command
    result = run_command(["ip", "-json", "address"])
    data = json.loads(result)
    interface_data = {}
    for item in data:
        name = item["ifname"]
        interface_data[name] = item
    # Build dataclass for storage and easier test assertion
    iface = NetworkInterface()
    if intf in interface_data.keys():
        iface.operstate = interface_data[intf]["operstate"]
        iface.ifname = interface_data[intf]["ifname"]
        iface.mac = interface_data[intf]["address"].replace(":", "")
    return iface


def get_iface_mac(iface: str):
    """Check iproute2 output for <iface> and return a MAC with a format like 000000111111"""
    iface_data = get_data_from_iproute2(iface)
    iface_mac = None
    if iface_data:
        if iface_data.mac:
            iface_mac = iface_data.mac.replace(":", "")
    if iface_mac:
        return iface_mac
    return ""


def setup_config(args):
    """Create the configuration (SSID, channel, interface, etc) for the CTX"""
    log = logging.getLogger(inspect.stack()[0][3])

    # load in config (a: from default location "/etc/wlanpi-ctx/config.ini" or b: from provided)
    if os.path.isfile(args.config):
        try:
            parser = load_config(args.config)

            # we want to work with a dict whether we have config.ini or not
            config = convert_configparser_to_dict(parser)
        except configparser.MissingSectionHeaderError as error:
            log.error("config file appears to be corrupt")
            config = {}
    else:
        log.warning("can not find config at %s", args.config)
        config = {}

    if "GENERAL" not in config:
        config["GENERAL"] = {}

    if "channel" not in config["GENERAL"]:
        config["GENERAL"]["channel"] = 36

    if "interface" not in config["GENERAL"]:
        config["GENERAL"]["interface"] = "wlan0"
        
    if "tx_interval" not in config["GENERAL"]:
        config["GENERAL"]["tx_interval"] = 0.001
        
    if "tx_payload_max" not in config["GENERAL"]:
        config["GENERAL"]["tx_payload_max"] = 512
        
    if "tx_payload_min" not in config["GENERAL"]:
        config["GENERAL"]["tx_payload_min"] = 64

    # handle args
    #  - args passed in take precedent over config.ini values
    #  - did user pass in options that over-ride defaults?
    if args.channel:
        config["GENERAL"]["channel"] = args.channel
    if args.frequency:
        config["GENERAL"]["frequency"] = args.frequency
        # user gave us freq, do not set value from config.ini
        config["GENERAL"]["channel"] = 0
    else:
        config["GENERAL"]["frequency"] = 0
    if args.interface:
        config["GENERAL"]["interface"] = args.interface
    if args.tx_interval:
        config["GENERAL"]["tx_interval"] = args.tx_interval
    if args.tx_payload_max:
        config["GENERAL"]["tx_payload_max"] = args.tx_payload_max
    if args.tx_payload_min:
        config["GENERAL"]["tx_payload_min"] = args.tx_payload_min

    # ensure channel 1 is an integer and not a bool
    try:
        ch = config.get("GENERAL").get("channel")
        if ch:
            ch = int(ch)
        config["GENERAL"]["channel"] = ch
    except KeyError:
        log.warning("config.ini does not have channel defined")

    # log.debug("config loaded is %s", config)

    return config


def strtobool(val):  # noqa: VNE002
    """Convert a string representation of truth to true (1) or false (0).
    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()  # noqa: VNE002
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))


def convert_configparser_to_dict(config: configparser.ConfigParser) -> Dict:
    """
    Convert ConfigParser object to dictionary.

    The resulting dictionary has sections as keys which point to a dict of the
    section options as key => value pairs.

    If there is a string representation of truth, it is converted from str to bool.
    """
    _dict: "Dict[str, Any]" = {}
    for section in config.sections():
        _dict[section] = {}
        for key, _value in config.items(section):
            try:
                _value = bool(strtobool(_value))  # type: ignore
            except ValueError:
                pass
            _dict[section][key] = _value
    return _dict


def load_config(config_file: str) -> configparser.ConfigParser:
    """Load in config from external file"""
    config = configparser.ConfigParser()
    config.read(config_file)
    return config


def validate(config) -> bool:
    """Validate minimum config to run is OK"""
    log = logging.getLogger(inspect.stack()[0][3])

    if not check_config_missing(config):
        return False

    try:
        ch = config.get("GENERAL").get("channel")
        if ch:
            log.debug("validating config for channel...")
            channel(ch)

        freq = config.get("GENERAL").get("frequency")
        if freq:
            log.debug("validating config for freq...")
            frequency(freq)
            
        intv = config.get("GENERAL").get("tx_interval")
        if intv:
            log.debug("validating config for tx_interval...")
            interval(ch)

        tx_payload_max = config.get("GENERAL").get("tx_payload_max")
        if tx_payload_max:
            log.debug("validating config for tx_payload_max...")
            payload_size(tx_payload_max)
            
        tx_payload_min = config.get("GENERAL").get("tx_payload_min")
        if tx_payload_min:
            log.debug("validating config for tx_payload_min...")
            payload_size(tx_payload_min)
            
    except ValueError:
        log.error("%s", sys.exc_info())
        sys.exit(signal.SIGABRT)

    return True


def check_config_missing(config: Dict) -> bool:
    """Check that the minimal config items exist"""
    log = logging.getLogger(inspect.stack()[0][3])
    try:
        if "GENERAL" not in config:
            raise KeyError("missing general section from configuration")
        options = config["GENERAL"].keys()
        if "interface" not in options:
            raise KeyError("missing interface from config")
        if "channel" not in options:
            raise KeyError("missing channel from config")

    except KeyError:
        log.error("%s", sys.exc_info()[1])
        return False
    return True


def run_command(cmd: list, suppress_output=False) -> str:
    """Run a single CLI command with subprocess and return stdout or stderr response"""
    cp = subprocess.run(
        cmd,
        encoding="utf-8",
        shell=False,
        check=False,
        capture_output=True,
    )

    if not suppress_output:
        if cp.stdout:
            return cp.stdout
        if cp.stderr:
            return cp.stderr

    return "completed process return code is non-zero with no stdout or stderr"


def get_frequency_bytes(channel: int) -> bytes:
    """Take a channel number, converts it to a frequency, and finally to bytes"""
    if channel == 14:
        freq = 2484
    if channel < 14:
        freq = 2407 + (channel * 5)
    elif channel > 14:
        freq = 5000 + (channel * 5)

    return freq.to_bytes(2, byteorder="little")


class Base64Encoder(json.JSONEncoder):
    """A Base64 encoder for JSON"""
    # example usage: json.dumps(bytes(frame), cls=Base64Encoder)

    # pylint: disable=method-hidden
    def default(self, obj):
        """Perform default Base64 encode"""
        if isinstance(obj, bytes):
            return b64encode(obj).decode()
        return json.JSONEncoder.default(self, obj)


def generate_run_message(config: Dict) -> None:
    """Create message to display to users screen"""
    interface = config["GENERAL"]["interface"]

    print()
    print("#/~>")
    print(
        f"Starting a fake AP using {interface} ({config['GENERAL']['mac']}) on channel {config['GENERAL']['channel']} ({config['GENERAL']['frequency']})"
    )
    print(
        f" - Transmitting QoS Data frames to 02:00:00:31:41:59 every {config['GENERAL']['tx_interval']} seconds"
    )
    print(
        f" - Payload is os.urandom(length) where length is a random integer between {config['GENERAL']['tx_payload_min']} and {config['GENERAL']['tx_payload_max']}"
    )
    print("#/~>")
    print()