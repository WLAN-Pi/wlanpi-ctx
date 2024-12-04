# -*- coding: utf-8 -*-
#
# ctx : a Wi-Fi client capability analyzer tool
# Copyright : (c) 2024 Josh Schmelzle
# License : BSD-3-Clause
# Maintainer : josh@joshschmelzle.com

"""
ctx.fakeap
~~~~~~~~~~

fake ap code to ctx
"""

# standard library imports
import inspect
import logging
import multiprocessing
import os
import random
import signal
import sys
from time import sleep

# suppress scapy warnings
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# third party imports
try:
    from scapy.all import LLC, SNAP, Dot11, Dot11QoS, RadioTap, Raw, Scapy_Exception
    from scapy.all import conf as scapyconf  # type: ignore
    from scapy.all import get_if_hwaddr
    from scapy.arch.unix import get_if_raw_hwaddr
except ModuleNotFoundError as error:
    if error.name == "scapy":
        print("required module scapy not found.")
    else:
        print(f"{error}")
    sys.exit(signal.SIGABRT)

DOT11_TYPE_DATA = 2
DOT11_SUBTYPE_DATA = 0x00
DOT11_SUBTYPE_QOS_DATA = 0x08


class TxData(multiprocessing.Process):
    """Handle Tx of fake AP frames"""

    def __init__(self, config):
        super(TxData, self).__init__()
        self.log = logging.getLogger(inspect.stack()[0][1].split("/")[-1])
        self.log.debug("ctx pid: %s; parent pid: %s", os.getpid(), os.getppid())
        self.log.debug("config passed to ctx: %s", config)
        if not isinstance(config, dict):
            raise ValueError(
                "configuration received in the TxData process is not a dictionary"
            )
        self.config = config
        self.interface: "str" = config.get("GENERAL").get("interface")

        channel: "str" = config.get("GENERAL").get("channel")
        if not channel:
            raise ValueError("cannot determine channel to ctx on")
        self.channel = int(channel)

        tx_interval: "str" = config.get("GENERAL").get("tx_interval")
        if not tx_interval:
            raise ValueError("cannot determine Tx interval for continuous Tx")
        self.tx_interval = float(tx_interval)

        tx_payload_min: "str" = config.get("GENERAL").get("tx_payload_min")
        if not tx_payload_min:
            raise ValueError("cannot determine minimum payload size")
        self.tx_payload_min = float(tx_payload_min)

        tx_payload_max: "str" = config.get("GENERAL").get("tx_payload_max")
        if not tx_payload_max:
            raise ValueError("cannot determine minimum payload size")
        self.tx_payload_max = float(tx_payload_max)

        scapyconf.iface = self.interface
        self.l2socket = None
        try:
            self.l2socket = scapyconf.L2socket(iface=self.interface)
        except OSError as error:
            if "No such device" in error.strerror:
                self.log.warning(
                    "TxData: no such device (%s) ... exiting ...", self.interface
                )
                sys.exit(signal.SIGALRM)
        if not self.l2socket:
            self.log.error(
                "TxData(): unable to create L2socket with %s ... exiting ...",
                self.interface,
            )
            sys.exit(signal.SIGALRM)
        self.log.debug(self.l2socket.outs)
        self.tx_interval = 0.102_400

        self.mac = self.get_mac(self.interface)

        dot11 = Dot11(
            type=DOT11_TYPE_DATA,
            subtype=DOT11_SUBTYPE_QOS_DATA,
            addr1="02:00:00:31:41:59",
            addr2=self.mac,
            addr3=self.mac,
        )

        self.data_frame = RadioTap() / dot11 / Dot11QoS() / LLC() / SNAP()

        self.log.info("starting QoS data frame transmissions")
        self.every(self.tx_interval, self.tx_data)

    def get_mac(self, interface: str) -> str:
        """Get the mac address for a specified interface"""
        try:
            mac = get_if_hwaddr(interface)
        except Scapy_Exception:
            mac = ":".join(format(x, "02x") for x in get_if_raw_hwaddr(interface)[1])
        return mac

    def generate_random_data(self, min=64, max=512):
        """Generate random payload data."""
        length = random.randint(min, max)
        return os.urandom(length)

    def every(self, interval, task) -> None:
        """Attempt to address beacon drift"""
        while True:
            task()
            sleep(interval)

    def tx_data(self) -> None:
        """Update and Tx QoS Data Frame"""
        payload = self.generate_random_data(
            min=self.tx_payload_min, max=self.tx_payload_max
        )
        data_frame = self.data_frame / Raw(load=payload)
        try:
            self.l2socket.send(data_frame)  # type: ignore
        except OSError as error:
            for event in ("Network is down", "No such device"):
                if event in error.strerror:
                    self.log.warning(
                        "tx_data(): network is down or no such device (%s) ... \ninterface may have disappeared ... check dmesg... \nexiting ...",
                        self.interface,
                    )
                    sys.exit(signal.SIGALRM)
