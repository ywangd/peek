"""Console script for peek."""
import argparse
import sys

from peek.peek import Repl


def main():
    """Console script for peek."""
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    Repl().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
