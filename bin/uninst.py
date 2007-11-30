#!/usr/bin/python

import os
import sys

script_path = os.path.realpath(os.path.abspath(sys.argv[0]))
topdir = os.path.dirname(os.path.dirname(script_path))
libdir = os.path.join(topdir, 'lib')

sys.path[0:0] = [libdir]

import reinteract
import reinteract.main