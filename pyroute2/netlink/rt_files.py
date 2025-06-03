"""Rt files parser

iproute2 got lot of "map" files, called rt_xxx for most of them,
this module is an helper for all files
"""

from pathlib import Path
from dataclasses import dataclass
from dataclasses import field


@dataclass(slots=True)
class IPRouteRtFile:
    filename: str

    id2name: dict[int, str] = field(default_factory=dict)
    name2id: dict[str, int] = field(default_factory=dict)

    # like iproute2 stop at first existing directory
    DIRECTORIES = (Path("/etc/iproute2/"), Path("/usr/share/iproute2/"))

    def __post_init__(self):
        self.load_files()

    def _iter_files(self, filepath):
        d_folder = Path(f'{filepath}.d')
        if filepath.exists():
            yield filepath
        if d_folder.exists():
            yield from (p for p in d_folder.iterdir() if p.suffix == '.conf')

    def iter_files(self):
        next_folder = True
        for folder in self.DIRECTORIES:
            for filepath in self._iter_files(folder / self.filename):
                next_folder = False
                yield filepath
            if not next_folder:
                return

    def load_files(self):
        self.id2name = {}
        self.name2id = {}

        for filename in self.iter_files():
            with filename.open(encoding='utf-8') as fp:
                for line in fp.readlines():
                    line = line.strip()
                    if not line or line[0] == '#':
                        continue
                    rt_id_as_str, rt_name = line.split()

                    if rt_id_as_str.startswith("0x"):
                        rt_id = int(rt_id_as_str[2:], 16)
                    elif ':' in rt_id_as_str:
                        # tc handle as class_id string
                        (major, minor) = [
                            int(x if x else '0', 16)
                            for x in rt_id_as_str.split(':')
                        ]
                        rt_id = (major << 16) | minor
                    else:
                        rt_id = int(rt_id_as_str)

                    if rt_id in self.id2name:
                        continue  # Accept only one rt_name by rt_id
                    self.id2name[rt_id] = rt_name
                    self.name2id[rt_name] = rt_id

    def get_rt_id(self, rt_name: str | int, default: int | None = None) -> int | None:
        """ Return id from the name.
        if rt_name is an int or digits() return it as int
        """
        if isinstance(rt_name, int):
            return rt_name
        if rt_name.isdigit():
            return int(rt_name)
        if default is None:
            return self.name2id[rt_name]
        return self.name2id.get(rt_name, default)
        
    def get_rt_name(self, rt_id: str | int, default: str | None = None) -> str | None:
        """ Return name from the id.
        name not found return id as str
        if the id is already a string return it
        """
        if isinstance(rt_id, str):
            return rt_id
        if default is None:
            return self.id2name.get(rt_id, rt_id)
        return self.id2name.get(rt_id, default)

    def __iter__(self):
        yield from self.id2name.items()


@dataclass(slots=True)
class EmatchMapFile(IPRouteRtFile):
    filename: str = 'ematch_map'


@dataclass(slots=True)
class NlProtosFile(IPRouteRtFile):
    filename: str = 'nl_protos'


@dataclass(slots=True)
class RtAddrProtosFile(IPRouteRtFile):
    filename: str = 'rt_addrprotos'


@dataclass(slots=True)
class RtDsfieldFile(IPRouteRtFile):
    filename: str = 'rt_dsfield'


@dataclass(slots=True)
class RtGroupFile(IPRouteRtFile):
    filename: str = 'rt_group'


@dataclass(slots=True)
class RtProtosFile(IPRouteRtFile):
    filename: str = 'rt_protos'


@dataclass(slots=True)
class RtRealmsFile(IPRouteRtFile):
    filename: str = 'rt_realms'


@dataclass(slots=True)
class RtScopesFile(IPRouteRtFile):
    filename: str = 'rt_scopes'


@dataclass(slots=True)
class RtTablesFile(IPRouteRtFile):
    filename: str = 'rt_tables'


@dataclass(slots=True)
class TcClsFile(IPRouteRtFile):
    filename: str = 'tc_cls'


def main(cls_list):
    for cls in cls_list.values():
        try:
            assert issubclass(cls, IPRouteRtFile) and not cls is IPRouteRtFile
        except (TypeError, AssertionError):
            continue

        cls = cls()
        print(f"====  Show rt maps for: {cls.filename} ===")
        print("get_rt_id('default') ==", cls.get_rt_id("default", "pas trouvé"))
        for id, name in cls:
            print(f"{id} {name}")


if __name__ == "__main__":
    main(locals())
