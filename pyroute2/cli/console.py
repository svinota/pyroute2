from __future__ import print_function

import re
import sys
import code
import socket
import getpass
from pprint import pprint
from pyroute2 import NDB
from pyroute2.common import basestring
from pyroute2.cli import t_dict
from pyroute2.cli.parser import Parser
try:
    import pdb
    HAS_PDB = True
except ImportError:
    HAS_PDB = False
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False


class Console(code.InteractiveConsole):
    def __init__(self, stdout=None):
        global HAS_READLINE
        self.db = NDB()
        self.ptr = self.db
        self.ptrname = None
        self.stack = []
        self.matches = []
        self.isatty = sys.stdin.isatty()
        self.prompt = ''
        self.stdout = stdout or sys.stdout
        self.set_prompt()
        code.InteractiveConsole.__init__(self)
        if HAS_READLINE:
            readline.parse_and_bind('tab: complete')
            readline.set_completer(self.completer)
            readline.set_completion_display_matches_hook(self.display)

    def close(self):
        self.db.close()

    def write(self, text=''):
        self.lprint(text)

    def pprint(self, text=''):
        pprint(text, stream=self.stdout)
        self.stdout.flush()

    def lprint(self, text='', end='\n'):
        print(text, file=self.stdout, end=end)
        self.stdout.flush()

    def help(self):
        self.lprint("Built-in commands: \n"
                    "debug\t-- run pdb (if installed)\n"
                    "exit\t-- exit cli\n"
                    "ls\t-- list current namespace\n"
                    ".\t-- print the current object\n"
                    ".. or ;\t-- one level up\n")

    def set_prompt(self, prompt=None):
        if self.isatty:
            if prompt is not None:
                self.prompt = '%s > ' % (prompt)
            else:
                self.prompt = '%s > ' % (self.ptr.__class__.__name__)
            self.prompt = '%s@%s : %s' % (getpass.getuser(),
                                          (socket
                                           .gethostname()
                                           .split('.')[0]),
                                          self.prompt)

    def convert(self, arg):
        if re.match('^[0-9]+$', arg):
            return int(arg)
        else:
            return arg

    def handle_statement(self, stmt):
        obj = None
        if stmt.name == 'debug':
            if HAS_PDB:
                pdb.set_trace()
            else:
                self.lprint('pdb is not available')
        elif stmt.name == 'exit':
            raise SystemExit()
        elif stmt.name == 'ls':
            self.lprint(dir(self.ptr))
        elif stmt.name == 'help':
            self.help()
        elif stmt.name == 'show':
            self.pprint(self.ptr)
        elif stmt.name == '.':
            self.lprint(repr(self.ptr))
        elif stmt.name == '..':
            if self.stack:
                self.ptr, self.ptrname = self.stack.pop()
            self.set_prompt(self.ptrname)
        else:
            if stmt.kind == t_dict:
                obj = self.ptr[stmt.kwarg]
            else:
                if isinstance(self.ptr, dict):
                    try:
                        obj = self.ptr.get(stmt.name, None)
                    except Exception:
                        pass
                if obj is None:
                    obj = getattr(self.ptr, stmt.name, None)

            if obj is None:
                if isinstance(self.ptr, dict):
                    self.ptr[stmt.name] = self.convert(stmt.argv[0])
                    return
                else:
                    raise KeyError()

            if hasattr(obj, '__call__'):
                try:
                    ret = obj(*stmt.argv, **stmt.kwarg)
                    if hasattr(obj, '__cptr__'):
                        obj = ret
                    else:
                        if hasattr(ret, 'generator'):
                            for line in ret:
                                self.lprint(line)
                        return
                except:
                    self.showtraceback()
                    return

            if isinstance(obj, (basestring, int, float)):
                if stmt.argv:
                    self.ptr[stmt.name] = self.convert(stmt.argv[0])
                else:
                    self.pprint(obj)
            else:
                self.stack.append((self.ptr, self.ptrname))
                self.ptr = obj
                self.ptrname = stmt.name
                self.set_prompt(stmt.name)

    def interact(self, readfunc=None):

        if readfunc is None:
            readfunc = self.raw_input

        if self.isatty:
            self.lprint("pyroute2 cli prototype")

        indent = 0
        while True:
            try:
                text = readfunc(self.prompt)
            except:
                self.lprint()
                self.close()
                break

            try:
                parser = Parser(text)
            except:
                self.showtraceback()
                continue
            for sentence in parser.sentences:
                if sentence.indent < indent:
                    if self.stack:
                        self.ptr, self.ptrname = self.stack.pop()
                indent = sentence.indent
                for stmt in sentence.statements:
                    try:
                        self.handle_statement(stmt)
                    except SystemExit:
                        self.close()
                        return
                    except KeyError:
                        self.lprint('object not found')
                    except:
                        self.showtraceback()

    def completer(self, text, state):
        if state == 0:
            d = [x for x in dir(self.ptr) if x.startswith(text)]
            if isinstance(self.ptr, dict):
                keys = [str(y) for y in self.ptr.keys()]
                d.extend([x for x in keys if x.startswith(text)])
            self.matches = d
        try:
            return self.matches[state]
        except:
            pass

    def display(self, line, matches, length):
        self.lprint()
        self.lprint(matches)
        self.lprint('%s%s' % (self.prompt, line), end='')


if __name__ == '__main__':
    Console().interact()
