"""Console script for peek."""
import argparse
import sys

from peek.peek import Peek


def main():
    """Console script for peek."""
    parser = argparse.ArgumentParser()

    parser.add_argument('--config', default='~/.peekrc',
                        help='Configuration file to load')

    parser.add_argument('-e', '--extra-config-option', action='append',
                        help='Extra configuration option to override')
    args = parser.parse_args()

    Peek(
        config_file=args.config,
        extra_config_options=args.extra_config_option).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
