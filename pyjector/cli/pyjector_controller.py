import argparse
import json
import logging
import sys

import pkg_resources

from pyjector import Pyjector


def main():
    parser = argparse.ArgumentParser(description='Control your projector from the command line.')
    parser.add_argument('device', help='The device you wish to control. ex benq')
    parser.add_argument('port', help='The serial port your device is connected to.')
    parser.add_argument('command', help='The command to send to the device. ex: power')
    parser.add_argument('action', help='The action to send to the device. ex: on')
    parser.add_argument('-s', '--serial', help='Extra PySerial config values.')
    parser.add_argument("-v", "--verbose", help="verbose output", action="store_const", dest="loglevel", const=logging.INFO, default=logging.WARNING,)
    parser.add_argument("-d", "--debug",   help="print debug",    action="store_const", dest="loglevel", const=logging.DEBUG,)
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel, format='%(created)f %(levelname)s %(message)s')

    if not pkg_resources.resource_exists(__name__, 'projector_configs/{device_id}.json'.format(device_id=args.device)):
        logging.error('Configuration file for "{device_id} not found at {resource_folder}.'.format(
            device_id=args.device,
            resource_folder=pkg_resources.resource_filename(__name__, 'projector_configs')
        ))
        sys.exit(1)

    with pkg_resources.resource_stream(
            __name__,
            'projector_configs/{device_id}.json'.format(device_id=args.device)
    ) as cf:
        pyjector = Pyjector(port=args.port, config=json.load(cf))

        command = getattr(pyjector, args.command)
        command(args.action)


if __name__ == '__main__':
    main()
