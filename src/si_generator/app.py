from __future__ import annotations

import sys

from . import cli, gui
from .chemdraw_names import main as chemdraw_names_main


CLI_FLAG = "--si-generator-cli"
CHEMDRAW_NAMES_FLAG = "--si-generator-chemdraw-names"


def main() -> int:
    args = sys.argv[1:]
    if args:
        if args[0] == CLI_FLAG:
            args = args[1:]
        elif args[0] == CHEMDRAW_NAMES_FLAG:
            return chemdraw_names_main(args[1:])
        return cli.main(args)
    gui.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
