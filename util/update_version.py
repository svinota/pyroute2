#!/usr/bin/env python
import subprocess
from pathlib import Path

version_module = "pyroute2/config/version.py"
version_output_file = "VERSION"
version_input_file = "VERSION"


def get_project_version():
    """
    Get the project version

    1. fetch version from git
    2. if not available, fallback to the version file in the repo
    """
    version = None

    try:
        git_top_level = Path(
            subprocess.check_output(
                ("git", "rev-parse", "--show-toplevel"),
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
        pyroute2_top_level = Path(__file__).parent.parent.absolute()
        # Only retrieve the git description from the pyroute2 directory
        if git_top_level == pyroute2_top_level:
            version = subprocess.check_output(
                ("git", "describe"), stderr=subprocess.DEVNULL
            ).decode("utf-8")
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    if version is None:
        with open(version_input_file, "r") as f:
            version = f.read()

    version = version.strip().split("-")

    if len(version) > 1:
        version = "{version[0]}.post{version[1]}".format(**locals())
    else:
        version = version[0]
    return version


if __name__ == "__main__":
    version = get_project_version()
    with open(version_module, "w") as f:
        f.write('__version__ = "%s"\n' % version)
    with open(version_output_file, "w") as f:
        f.write("%s\n" % version)
