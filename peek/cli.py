"""Console script for peek."""
import argparse
import sys

from peek.peek import Peek


def main():
    """Console script for peek."""
    parser = argparse.ArgumentParser()

    parser.add_argument('-b', '--batch', action='store_true',
                        help='Take input from stdin and run in batch mode')
    parser.add_argument('--config', default='~/.peekrc',
                        help='Configuration file to load')

    parser.add_argument('-e', '--extra-config-option', action='append',
                        help='Extra configuration option to override')
    args = parser.parse_args()

    peek = Peek(
        batch_mode=args.batch,
        config_file=args.config,
        extra_config_options=args.extra_config_option
    )
    if args.batch:
        stdin_read = sys.stdin.read()
        peek.execute_command(stdin_read)
    else:
        peek.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
