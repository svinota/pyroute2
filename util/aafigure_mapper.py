import io
import sys
import contextlib


ret = io.StringIO()

with contextlib.ExitStack() as ctx:
    map_file = ctx.enter_context(open(sys.argv[1], 'r'))
    img_file = ctx.enter_context(open(sys.argv[2], 'r'))

    mapping = {
        key.strip(): value.strip()
        for (key, value) in [x.split('|') for x in map_file.readlines()]
    }
    for line in img_file.readlines():
        for key, value in mapping.items():
            line = line.replace(key, f'  <a href="{value}">{key}</a>')
        ret.write(line)

with open(sys.argv[2], 'w') as img_file:
    img_file.write(ret.getvalue())
