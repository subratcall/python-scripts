#!/usr/bin/python3
# btrfs-snapshot a set of btrfs filesystems.
# Copyright (C) 2015 Stuart Pook (http://www.pook.it)
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.  This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.  You should have received a copy of the GNU General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import tempfile
import subprocess
import shlex
import argparse
import configparser
import pytz
import pytz.reference
import datetime
import dateutil.parser

def timestamp():
    local_system_utc = pytz.utc.localize(datetime.datetime.utcnow())
    rounded = local_system_utc.astimezone(pytz.reference.LocalTimezone()).replace(microsecond=0)
    r = rounded.isoformat()
# parse using
    assert dateutil.parser.parse(r) == rounded
    return r

def verbose(args, *opts):
    if args.verbosity:
        print(os.path.basename(sys.argv[0]) + ":", *opts, file=sys.stderr)

def warn(*opts):
    print(os.path.basename(sys.argv[0]) + ":", *opts, file=sys.stderr)

def error(*opts):
    warn(*opts)
    sys.exit(3)

def quote_command(command):
    return " ".join(shlex.quote(x) for x in command)

def check_pipe(command, p, stdout, options):
    if p.wait() != 0:
        if stdout is None:
            r = ""
        else:
            stdout.seek(0)
            r = ": " + stdout.read().rstrip()
        warn(quote_command(command), "failed (%d)%s" % (p.returncode, r))
        return 1
    return 0

def get_stdout(options):
    if options.verbosity > 0:
        return None
    return tempfile.TemporaryFile(mode='w+')

def check_call(command, options):
    verbose(options, quote_command(command))
    if options.dryrun:
        return
    stdout = get_stdout(options)
    p = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout)
    return check_pipe(command, p, stdout, options) == 0

def snapshot(src, dst_dir, options):
    dst = os.path.join(dst_dir, options.timestamp)
    return check_call([options.btrfs, "subvolume", "snapshot", "-r", src, dst], options)

def snapshot_with_config(options):
    config = configparser.ConfigParser()
    with open(options.config) as f:
        config.read_file(f)
    ok = True
    for section_name in config.sections():
        section = config[section_name]
        src = section.get("source", None)
        if src == None:
            src = os.path.join(section.get("sourcedirectory", None), section_name)
        dst = section.get("destination", None)
        if dst == None:
            dst = os.path.join(section.get("destinationdirectory", None), section_name)
#        verbose(options, "Section: %s %s -> %s" % (section_name, src, dst))
        ok = snapshot(src, dst, options) and ok
    return ok

def snapshot_directories(src_dir, dst_dir, options):
    ok = True
    for subdir in os.listdir(src_dir):
        ok = snapshot(os.path.join(src_dir, subdir), os.path.join(dst_dir, subdir), options) and ok
    return ok

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    parser.add_argument('--config', default="/etc/local/btrfs-snapshots", help='config file')
    parser.add_argument('--btrfs', default="btrfs", help='btrfs command')
    parser.add_argument('--timestamp', default=timestamp(), help='timestamp for new snapshots')
    parser.add_argument('-D', '--directories', action='store_true', help='do subdirectories of arguments')
    parser.add_argument('-n', '--dryrun', action='store_true', help='do not execute')

    parser.add_argument('args', nargs=argparse.REMAINDER, help='directories')

    options = parser.parse_args()

    if options.config:
        ok = snapshot_with_config(options)
    elif options.directories and len(options.args) >= 2:
        ok = True
        for src in options.args[0:-1]:
            ok = snapshot_directories(src, options.args[-1], options) and ok
    elif len(options.args) == 2:
        ok = snapshot(options.args[0], options.args[-1], options)
    else:
        parser.print_help()
        sys.exit("bad arguments")
    sys.exit(0 if ok else 8)

if __name__ == "__main__":
    main()
