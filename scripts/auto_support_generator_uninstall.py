from __future__ import annotations

import sys

from auto_support_generator_installer import main


if __name__ == "__main__":
    raise SystemExit(main(["--uninstall", *sys.argv[1:]]))
