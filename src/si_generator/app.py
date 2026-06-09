from __future__ import annotations

import sys

from . import cli, gui


CLI_FLAG = "--si-generator-cli"


def main() -> int:
    args = sys.argv[1:]
    if args:
        if args[0] == CLI_FLAG:
            args = args[1:]
        return cli.main(args)
    gui.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
