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
            ret.append(repr(record))
            counter += 1
            if counter > MAX_REPORT_LINES:
                ret.append('(...)')
                break
        return '\n'.join(ret)

    def __len__(self):
        counter = 0
        for _ in self.generator:
            counter += 1
        return counter
