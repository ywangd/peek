"""Console script for peek."""
import argparse
import sys

from peek import __version__
from peek.config import config_location
from peek.peekapp import PeekApp


def main():
    """Console script for peek."""
    parser = argparse.ArgumentParser()

    parser.add_argument('input', nargs='*',
                        help='script files')

    parser.add_argument('--config', default=config_location() + 'peekrc',
                        help='Configuration file to load')

    parser.add_argument('-e', '--extra-config-option', action='append',
                        help='Extra configuration option to override')

    parser.add_argument('--name',
                        help='A friendly name for the connection')
    parser.add_argument('--hosts', default='localhost:9200',
                        help='ES hosts to connect to')
    parser.add_argument('--cloud_id',
                        help='Elastic Cloud ID')
    parser.add_argument('--username',
                        help='Username')
    parser.add_argument('--password',
                        help='Password')
    parser.add_argument('--api_key',
                        help='API key of format id:key')
    parser.add_argument('--token',
                        help='Token for authentication')
    parser.add_argument('--use_ssl', action='store_true',
                        help='Enable TLS for connecting to ES')
    parser.add_argument('--verify_certs', action='store_true',
                        help='Verify server certificate')
    parser.add_argument('--assert_hostname', action='store_true',
                        help='Verify hostname')
    parser.add_argument('--ca_certs',
                        help='Location of CA certificates')
    parser.add_argument('--client_cert',
                        help='Location of client certificate')
    parser.add_argument('--client_key',
                        help='Location of client private key')
    parser.add_argument('--force_prompt', action='store_true',
                        help='Force prompting for password')
    parser.add_argument('--no_prompt', action='store_true',
                        help='Do not prompt for password')

    parser.add_argument('-V', '--version', action='version',
                        version=__version__)

    ns = parser.parse_args()

    isatty = sys.stdin.isatty()
    batch_mode = (not isatty) or bool(ns.input)

    peek = PeekApp(
        batch_mode=batch_mode,
        config_file=ns.config,
        extra_config_options=ns.extra_config_option,
        cli_ns=ns,
    )
    if not batch_mode:
        peek.run()
    else:
        if ns.input:
            for f in ns.input:
                with open(f) as ins:
                    peek.process_input(ins.read())
        else:
            stdin_read = sys.stdin.read()
            peek.process_input(stdin_read)

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
