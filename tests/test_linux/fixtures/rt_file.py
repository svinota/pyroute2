from pathlib import Path

from pyroute2.netlink import rt_files


class CreateRtFile:

    def __init__(self, tmpdir):
        self.tmpdir = tmpdir
        rt_files.IPRouteRtFile.DIRECTORIES = [Path(self.tmpdir)]

    def create(self, rt_file, file_as_dict):
        with (self.tmpdir / rt_file.get_rt_filename()).open("w+") as fp:
            for key, value in file_as_dict.items():
                fp.write(f"{key} {value}\n")
