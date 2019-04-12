from pyroute2.common import basestring

MAX_REPORT_LINES = 100


class Report(object):

    def __init__(self, generator):
        self.generator = generator

    def __iter__(self):
        return self.generator

    def __repr__(self):
        counter = 0
        ret = []
        for record in self.generator:
            if isinstance(record, basestring):
                ret.append(record)
            else:
                ret.append(repr(record))
                ret.append('\n')
            counter += 1
            if counter > MAX_REPORT_LINES:
                ret.append('(...)')
                break
        if ret[-1] == '\n':
            ret.pop()
        return ''.join(ret)
