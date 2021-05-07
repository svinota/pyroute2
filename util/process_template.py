import sys
import json


class Formatter(dict):

    def __missing__(self, key):
        return '{%s}' % key


name_in, name_defs, name_out = sys.argv[1:]

with open(name_in, 'r') as file_in:
    with open(name_out, 'w') as file_out:
        with open(name_defs, 'r') as file_defs:
            defs = json.load(file_defs)
            lists = []
            for key, value in defs.items():
                if isinstance(value, list):
                    lists.append(key)
        for line in file_in.readlines():
            for list_name in lists:
                if '{%s}' % list_name in line:
                    for entry in defs[list_name]:
                        file_out.write(
                            line.format_map(
                                Formatter(**{list_name: entry})))
                    break
            else:
                file_out.write(line.format_map(Formatter(**defs)))
