from __future__ import print_function

import sys
from collections import namedtuple
from pyroute2.common import basestring
from pyroute2.cli import t_dict
from pyroute2.cli import t_stmt
from pyroute2.cli.parser import Parser


class Session(object):
    def __init__(self, ndb, stdout=None, ptrname_callback=None):
        self.db = ndb
        self.ptr = self.db
        self._ptrname = None
        self._ptrname_callback = ptrname_callback
        self.stack = []
        self.prompt = ''
        self.stdout = stdout or sys.stdout

    @property
    def ptrname(self):
        return self._ptrname

    @ptrname.setter
    def ptrname(self, name):
        self._ptrname = name
        if self._ptrname_callback is not None:
            self._ptrname_callback(name)

    def stack_pop(self):
        self.ptr, self.ptrname = self.stack.pop()
        return (self.ptr, self.ptrname)

    def lprint(self, text='', end='\n'):
        if not isinstance(text, basestring):
            text = str(text)
        self.stdout.write(text)
        if end:
            self.stdout.write(end)
        self.stdout.flush()

    def handle_statement(self, stmt, token):
        obj = None
        if stmt.name == 'exit':
            raise SystemExit()
        elif stmt.name == 'ls':
            self.lprint(dir(self.ptr))
        elif stmt.name == '.':
            self.lprint(repr(self.ptr))
        elif stmt.name == '..':
            if self.stack:
                self.ptr, self.ptrname = self.stack.pop()
        else:
            if stmt.kind == t_dict:
                obj = self.ptr[stmt.kwarg]
            elif stmt.kind == t_stmt:
                if isinstance(self.ptr, dict):
                    try:
                        obj = self.ptr.get(stmt.name, None)
                    except Exception:
                        pass
                if obj is None:
                    obj = getattr(self.ptr, stmt.name, None)

            if hasattr(obj, '__call__'):
                try:
                    nt = next(token)
                except StopIteration:
                    nt = (namedtuple('Token',
                                     ('kind',
                                      'argv',
                                      'kwarg'))(t_dict, [], {}))

                if nt.kind != t_dict:
                    raise TypeError('function arguments expected')

                try:
                    ret = obj(*nt.argv, **nt.kwarg)
                    if hasattr(obj, '__cli_cptr__'):
                        obj = ret
                    elif hasattr(obj, '__cli_publish__'):
                        if hasattr(ret, 'generator') or hasattr(ret, 'next'):
                            for line in ret:
                                if isinstance(line, basestring):
                                    self.lprint(line)
                                else:
                                    self.lprint(repr(line))
                        else:
                            self.lprint(ret)
                        return
                    elif isinstance(ret, (bool, basestring, int, float)):
                        self.lprint(ret)
                        return
                    else:
                        return
                except:
                    import traceback
                    traceback.print_exc()
                    return
            else:
                if isinstance(self.ptr, dict) and not isinstance(obj, dict):
                    try:
                        nt = next(token)
                        if nt.kind == t_stmt:
                            self.ptr[stmt.name] = nt.name
                        elif nt.kind == t_dict and nt.argv:
                            self.ptr[stmt.name] = nt.argv
                        elif nt.kind == t_dict and nt.kwarg:
                            self.ptr[stmt.name] = nt.kwarg
                        else:
                            raise TypeError('failed setting a key/value pair')
                        return
                    except NotImplementedError:
                        raise KeyError()
                    except StopIteration:
                        pass

            if obj is None:
                raise KeyError()
            elif isinstance(obj, (basestring, int, float)):
                self.lprint(obj)
            else:
                self.stack.append((self.ptr, self.ptrname))
                self.ptr = obj
                if hasattr(obj, 'key_repr'):
                    self.ptrname = obj.key_repr()
                else:
                    self.ptrname = stmt.name
                return True

        return

    def handle_sentence(self, sentence, indent):
        if sentence.indent < indent:
            if self.stack:
                self.ptr, self.ptrname = self.stack.pop()
        indent = sentence.indent
        iterator = iter(sentence)
        rcode = None
        rcounter = 0
        try:
            for stmt in iterator:
                try:
                    rcode = self.handle_statement(stmt, iterator)
                    if rcode:
                        rcounter += 1
                except SystemExit:
                    self.close()
                    return
                except KeyError:
                    self.lprint('object not found')
                    rcode = False
                    return indent
                except:
                    import traceback
                    traceback.print_exc()
        finally:
            if not rcode:
                for _ in range(rcounter):
                    self.ptr, self.ptrname = self.stack.pop()
        return indent

    def handle(self, text, indent=0):
        parser = Parser(text)
        for sentence in parser.sentences:
            indent = self.handle_sentence(sentence, indent)
        return indent
