import sys

buf = []

text = sys.stdin.read().split('\n')
for line in text:

    if line.startswith('.. code-block::'):
        buf[0] += ':'
        buf.pop(1)
        continue

    buf.append(line)

    if len(buf) > 2:
        print(buf.pop(0))

print(buf[0])
