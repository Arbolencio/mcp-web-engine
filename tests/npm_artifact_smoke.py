"""Smoke the actual installed npm command shim on each supported runner OS."""
import argparse
import sys
from pathlib import Path


def installed_command(prefix, platform=sys.platform):
    executable = Path(prefix) / 'node_modules' / '.bin' / 'mcp-web-engine'
    if platform == 'win32':
        return ['cmd', '/d', '/c', str(executable.with_suffix('.cmd'))]
    return [str(executable)]


if __name__ == '__main__':
    from artifact_smoke import smoke
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prefix')
    smoke(installed_command(parser.parse_args().prefix))
