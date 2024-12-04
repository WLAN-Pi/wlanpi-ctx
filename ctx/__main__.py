# -*- coding: utf-8 -*-
#
# ctx : a Wi-Fi client capability analyzer tool
# Copyright : (c) 2024 Josh Schmelzle
# License : BSD-3-Clause
# Maintainer : josh@joshschmelzle.com

"""
ctx
~~~

a continuous random data frame transmitter
"""

import os
import platform
import sys


def main():
    """Set up args and start the ctx manager"""
    from . import helpers, manager

    parser = helpers.setup_parser()
    args = parser.parse_args()

    manager.start(args)


def init():
    """Handle main init"""
    # hard set no support for non linux platforms
    if "linux" not in sys.platform:
        sys.exit(
            "{0} only works on Linux... exiting...".format(os.path.basename(__file__))
        )

    # hard set no support for python < v3.9
    if sys.version_info < (3, 9):
        sys.exit(
            "{0} requires Python version 3.9 or higher...\nyou are trying to run with Python version {1}...\nexiting...".format(
                os.path.basename(__file__), platform.python_version()
            )
        )

    if __name__ == "__main__":
        sys.exit(main())


init()
