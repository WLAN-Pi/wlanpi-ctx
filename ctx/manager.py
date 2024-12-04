# -*- coding: utf-8 -*-
#
# ctx : a Wi-Fi client capability analyzer tool
# Copyright : (c) 2024 Josh Schmelzle
# License : BSD-3-Clause
# Maintainer : josh@joshschmelzle.com


"""
ctx.manager
~~~~~~~~~~~

handle ctx
"""

# standard library imports
import argparse
import inspect
import logging
import multiprocessing as mp
import os
import platform
import signal
import sys
from time import sleep

# third party imports
import scapy  # type: ignore
from scapy.all import rdpcap  # type: ignore

# app imports
from . import helpers
from .__init__ import __version__
from .constants import _20MHZ_FREQUENCY_CHANNEL_MAP
from .interface import Interface, InterfaceError

# things break when we use spawn
# from multiprocessing import set_start_method
# set_start_method("spawn")


__PIDS = []
__PIDS.append(("main", os.getpid()))
__IFACE = Interface()


def removeVif():
    """Remove the vif we created if exists"""
    if __IFACE.requires_vif and not __IFACE.removed:
        log = logging.getLogger(inspect.stack()[0][3])
        log.debug("Removing monitor vif ...")
        __IFACE.reset_interface()
        __IFACE.removed = True


def receiveSignal(signum, _frame):
    """Handle noisy keyboardinterrupt"""
    for name, pid in __PIDS:
        # We only want to print exit messages once as multiple processes close
        if name == "main" and os.getpid() == pid:
            if __IFACE.requires_vif:
                removeVif()
            if signum == 2:
                print("\nDetected SIGINT or Control-C ...")
            if signum == 15:
                print("Detected SIGTERM ...")


signal.signal(signal.SIGINT, receiveSignal)
signal.signal(signal.SIGTERM, receiveSignal)


def are_we_root() -> bool:
    """Do we have root permissions?"""
    if os.geteuid() == 0:
        return True
    else:
        return False


def start(args: argparse.Namespace):
    """Begin work"""
    log = logging.getLogger(inspect.stack()[0][3])

    if args.pytest:
        sys.exit("pytest")

    if not are_we_root():
        log.error("ctx must be run with root permissions... exiting...")
        sys.exit(-1)

    helpers.setup_logger(args)

    log.debug("%s version %s", __name__.split(".")[0], __version__)
    log.debug("python platform version is %s", platform.python_version())
    scapy_version = ""
    try:
        scapy_version = scapy.__version__
        log.debug("scapy version is %s", scapy_version)
    except AttributeError:
        log.exception("could not get version information from scapy.__version__")
        log.debug("args: %s", args)
    config = helpers.setup_config(args)

    if args.list_interfaces:
        __IFACE.print_interface_information()
        sys.exit(0)

    running_processes = []
    finished_processes = []
    parent_pid = os.getpid()
    log.debug("%s pid %s", __name__, parent_pid)

    if helpers.validate(config):
        log.debug("validated config %s", config)
    else:
        log.error("configuration validation failed... exiting...")
        sys.exit(-1)

    from .fakeap import TxData

    iface_name = config.get("GENERAL").get("interface")
    __IFACE.name = iface_name

    try:
        if args.no_interface_prep:
            log.warning(
                "user provided `--noprep` argument meaning ctx will not handle staging the interface"
            )
            # get channel from `iw`
            __IFACE.no_interface_prep = True
            __IFACE.setup()

            # setup should have detected a mac address
            config["GENERAL"]["mac"] = __IFACE.mac
            # need to set channel in config for banner
            if __IFACE.channel:
                config["GENERAL"]["channel"] = __IFACE.channel
            # need to set freq in config for banner
            if __IFACE.frequency:
                config["GENERAL"]["frequency"] = __IFACE.frequency
            log.debug("finish interface setup with no staging ...")
        else:
            # get channel from config setup by helpers.py (either passed in via CLI option or config.ini)
            channel = int(config.get("GENERAL").get("channel"))
            freq = int(config.get("GENERAL").get("frequency"))
            if channel != 0:
                # channel was provided, map it:
                for freq, ch in _20MHZ_FREQUENCY_CHANNEL_MAP.items():
                    if channel == ch:
                        __IFACE.frequency = freq
                        __IFACE.channel = ch
                        break
            if freq != 0:
                # freq was provided
                __IFACE.channel = _20MHZ_FREQUENCY_CHANNEL_MAP.get(freq, 0)
                if __IFACE.channel != 0:
                    __IFACE.frequency = freq
                else:
                    raise InterfaceError(
                        "could not determine channel from frequency (%s)", freq
                    )
            # if we made it here, make sure the config matches up
            config["GENERAL"]["channel"] = __IFACE.channel
            config["GENERAL"]["frequency"] = __IFACE.frequency

            # run interface setup
            __IFACE.setup()

            # setup should have detected a mac address
            config["GENERAL"]["mac"] = __IFACE.mac

            if __IFACE.requires_vif:
                # we require using a mon interface, update config so our subprocesses find it
                config["GENERAL"]["interface"] = __IFACE.mon
            __IFACE.stage_interface()
            log.debug("finish interface setup and staging ...")
    except InterfaceError:
        log.exception("problem interface staging ... exiting ...", exc_info=True)
        sys.exit(-1)

    helpers.generate_run_message(config)

    log.debug("ctx process")
    txdata = mp.Process(
        name="txdata",
        target=TxData,
        args=(config,), # What this looks like with one element because this param needs to be a tuple: args=(config,),
    )
    running_processes.append(txdata)
    txdata.start()
    __PIDS.append(("txdata", txdata.pid))  # type: ignore

    shutdown = False

    # keep main process alive until all subprocesses are finished or closed
    while running_processes:
        sleep(0.1)
        for process in running_processes:
            # if exitcode is None, it has not stopped yet.
            if process.exitcode is not None:
                if __IFACE.requires_vif and not __IFACE.removed:
                    removeVif()
                log.debug("shutdown %s process (%s)", process.name, process.exitcode)
                running_processes.remove(process)
                finished_processes.append(process)
                shutdown = True

            if shutdown:
                process.kill()
                process.join()
