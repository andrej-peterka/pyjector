"""Control your projector via serial port.

.. moduleauthor:: John Brodie <john@brodie.me>

"""
from time import sleep
import copy
import logging

import serial


class CommandFailedError(Exception):
    """A command failed, usually due to an invalid state change."""


class CommandExceptionError(Exception):
    """An executed command caused the device to return an error."""


class InvalidConfigError(Exception):
    """Loading the configuration failed as it is invalid."""


class InvalidCommandError(Exception):
    """The given command or action is invalid for the specified device."""


class Pyjector(object):

    possible_pyserial_settings = [
        'port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout',
        'xonxoff', 'rtscts', 'dsrdtr', 'writeTimeout', 'InterCharTimeout',
    ]
    pyserial_config_converter = {
        'bytesize': {
            5: serial.FIVEBITS,
            6: serial.SIXBITS,
            7: serial.SEVENBITS,
            8: serial.EIGHTBITS,
        },
        'parity': {
            'none': serial.PARITY_NONE,
            'even': serial.PARITY_EVEN,
            'odd': serial.PARITY_ODD,
            'mark': serial.PARITY_MARK,
            'space': serial.PARITY_SPACE,
        },
        'stopbits': {
            1: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2: serial.STOPBITS_TWO,
        },

    }

    def __init__(
            self,
            port=None,
            config=None,
            **kwargs
    ):
        """Initialize a new Pyjector object.

        :param port: The device name or port number your device is connected
            to. If left as ``None``, you must call :func:`open` with the port
            before issuing commands.

        :param config: The configuration dict to use

        :param **kwargs: Any extra keyword args will be passed to the internal
            :mod:`pyserial` :class:`serial.Serial` object, and will override
            any device settings specified in the command set.

        """
        self.port = port
        self.config = config or {}
        if kwargs:
            self.config.update(kwargs)

        self._validate_config()

        self.pyserial_config = self.get_pyserial_config()
        self.serial = self._initialize_pyserial(port)

        self._create_commands()

    def _validate_config(self):
        """Do basic sanity-checking on the loaded `config`."""
        if 'serial' not in self.config:
            raise InvalidConfigError(
                'Configuration does not contain needed serial'
                'config values. Add a `serial` section to the config.'
            )
        if ('command_list' not in self.config or
                len(self.config['command_list']) == 0):
            raise InvalidConfigError(
                'Configuration does not define any commands. '
                'Add a `command_list` section to the config.'
            )

    def get_pyserial_config(self):
        """Get the :mod:`pyserial` config values from the device config.

        This also checks that config values are sane, and casts them to
        the appropriate type, as needed.

        :returns: dict -- The config values for :class:`serial.Serial`.
        :raises: InvalidConfigError

        """
        serial_config = self.config['serial']
        for key, value in serial_config.items():
            if key not in self.possible_pyserial_settings:
                raise InvalidConfigError(
                    'Configuration specifies a serial '
                    'setting "{0}" not recognized by pyserial. Check '
                    'http://pyserial.sourceforge.net/pyserial_api.html'
                    'for valid settings'.format(
                        key)
                )
            if key in self.pyserial_config_converter:
                try:
                    serial_config[key] = (
                        self.pyserial_config_converter[key][value])
                except KeyError:
                    raise InvalidConfigError(
                        'Configuration specifies a serial '
                        'setting for "{0}" for key "{1}" not recognized '
                        'by pyserial. Check '
                        'http://pyserial.sourceforge.net/pyserial_api.html'
                        'for valid settings'.format(
                            value, key)
                    )
        return serial_config

    def _initialize_pyserial(self, port):
        """Initialize the internal :class:`serial.Serial` object."""
        return serial.Serial(port=port, **self.pyserial_config)

    def _send(self, data):
        logging.debug("_send: " + repr(data))
        self.serial.write(data.encode())

    def _recv(self, size=1):
        data = self.serial.read(size)
        if data:
            logging.debug("_recv: " + repr(data))
        return data

    def _do_handshake(self):
        h = self.config.get('handshake')
        if h is None:
            return
        self._send(h['send'])
        sleep(h['wait'])
        expected = h['expect']
        resp = self._recv(len(expected))
        if resp != expected:
            logging.error("unexpected response to handshake " + repr(resp))

    def _command_handler(self, command, action):
        """Send the `command` and `action` to the device.

        :param command: The command to send, for example, "power".
        :param action: The action to send, for example, "on".

        :returns: str -- The response from the device.

        :raises: InvalidCommandError if `action` is not valid for `command`.

        """
        if action not in self.get_actions_for_command(command):
            raise InvalidCommandError(
                '{0} is not a valid action for comand {1}'.format(
                    action, command)
            )
        command_string = self._create_command_string(command, action)
        logging.info("send: " + repr(command_string))
        self._do_handshake()
        self._send(command_string)
        sleep(self.config.get('wait_time', 1))
        response = self.get_response()
        logging.info("recv: " + repr(response))
        self._check_response(response)
        return response

    def _strip_response(self, response):
        rs = self.config.get('right_surround', '')
        ls = self.config.get('left_surround', '')
        return response.rstrip(rs).lstrip(ls)

    def _check_response(self, response):
        """Check for errors in the response."""
        if response is None:
            return
        known_responses = self.config.get('known_responses')
        if known_responses:
            response = self._strip_response(response)
            if response in known_responses:
                print known_responses[response]
                return
            else:
                raise CommandFailedError(
                    'Received an unknown response',
                    response
                )
        failed_message = self.config.get('command_failed_message')
        if failed_message is not None and failed_message in response:
            raise CommandFailedError(
                'Command failed! This is likely due to an invalid state '
                'change.'
            )
        exception_message = self.config.get('exception_message')
        if exception_message is not None and exception_message in response:
            raise CommandExceptionError(
                'Command caused an exception on the device. Your command '
                'is likely invalid, check your json projector config!'
            )

    def _create_commands(self):
        """Add commands to class."""
        # TODO: Clean this up.
        def _create_handler(command):
            def handler(action):
                return self._command_handler(command, action)
            return handler
        for command in self.command_spec:
            setattr(self, command, _create_handler(command))

    def get_response(self):
        """Get any message waiting in the serial port buffer.

        :returns: str -- Response from the device, empty string if no response.

        """
        response = ''
        while self.serial.inWaiting() > 0:
            response += self._recv(1)
        return response

    def _create_command_string(self, command, action):
        """Create a command string ready to send to the device.

        .. note:: The `command` param will be translated from english
        to the proper command for the device.

        """
        config = self.config

        serial_command = self.command_spec[command]['command']
        serial_action = actual_action = self.command_spec[command]['actions'][action]
        if isinstance(serial_action, dict):
            actual_action = serial_action.pop('action')
            config = copy.deepcopy(config)
            config.update(serial_action)

        command_string = (
            '{left_surround}{command}{seperator}'
            '{action}{right_surround}'.format(
                left_surround=config.get('left_surround', ''),
                command=serial_command,
                seperator=config.get('seperator', ''),
                action=actual_action,
                right_surround=config.get('right_surround', ''),
            )
        )
        return command_string

    def get_actions_for_command(self, command):
        """Get a list of all valid actions for a given command."""
        return self.command_spec.get(command, {}).get('actions').keys()

    @property
    def command_list(self):
        """Get a list of all commands.

        :returns: dict -- List of valid commands.

        """
        return self.config['command_list'].keys()

    @property
    def command_spec(self):
        """Return all command specifications.

        :returns: dict -- All command specs, with the pattern:
            "<alias>": {
                "command": "<serial_command>",
                "actions": {
                    "<alias>": "<serial_command>",
                    ...,
                },
            },
            ...
        """
        return self.config['command_list']
