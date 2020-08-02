"""Console script for peek."""
import argparse
import sys

from peek.config import config_location
from peek.peekapp import PeekApp


def main():
    """Console script for peek."""
    parser = argparse.ArgumentParser()

    parser.add_argument('--config', default=config_location() + 'peekrc',
                        help='Configuration file to load')

    parser.add_argument('-e', '--extra-config-option', action='append',
                        help='Extra configuration option to override')

    parser.add_argument('--hosts', default='localhsot:9200',
                        help='ES hosts to connect to')
    parser.add_argument('--auth_type', default='userpass',
                        choices=('userpass', 'apikey', 'token', 'saml', 'oidc', 'krb', 'pki'),
                        help='Authentication type')
    parser.add_argument('--username',
                        help='Username')
    parser.add_argument('--password',
                        help='Password')
    parser.add_argument('--api-key',
                        help='API key of format id:key')
    parser.add_argument('--use-ssl', action='store_true',
                        help='Enable TLS for connecting to ES')
    parser.add_argument('--verify-certs', action='store_true',
                        help='Verify server certificate')
    parser.add_argument('--ca-certs',
                        help='Location of CA certificates')
    parser.add_argument('--client-cert',
                        help='Location of client certificate')
    parser.add_argument('--client-key',
                        help='Location of client private key')
    parser.add_argument('--force-prompt', action='store_true',
                        help='Force prompting for password')
    parser.add_argument('--no-prompt', action='store_true',
                        help='Do not prompt for password')

    ns = parser.parse_args()

    isatty = sys.stdin.isatty()
    peek = PeekApp(
        batch_mode=not isatty,
        config_file=ns.config,
        extra_config_options=ns.extra_config_option,
        cli_ns=ns,
    )
    if isatty:
        peek.run()
    else:
        stdin_read = sys.stdin.read()
        peek.process_input(stdin_read)

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
