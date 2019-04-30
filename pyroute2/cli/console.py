from __future__ import print_function

import sys
import code
import socket
import getpass
from pprint import pprint
from collections import namedtuple
from pyroute2 import NDB
from pyroute2.common import basestring
from pyroute2.cli import t_dict
from pyroute2.cli import t_stmt
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
    def __init__(self, stdout=None, debug=None, sources=None):
        global HAS_READLINE
        self.db = NDB(debug=debug, sources=sources)
        self.db.config = {'show_format': 'json'}
        self.ptr = self.db
        self.ptrname = None
        self.stack = []
        self.log = []
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
        self.log.append(("pprint", text))
        pprint(text, stream=self.stdout)
        self.stdout.flush()

    def lprint(self, text='', end='\n'):
        self.log.append(("lprint", text))
        print(text, file=self.stdout, end=end)
        self.stdout.flush()

    def help(self):
        self.lprint("Built-in commands: \n"
                    "pdb\t-- run pdb (if installed)\n"
                    "exit\t-- exit cli\n"
                    "ls\t-- list current namespace\n"
                    ".\t-- print the current object\n"
                    ".. or Ctrl-D\t-- one level up\n")

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

    def handle_statement(self, stmt, token):
        obj = None
        if stmt.name == 'pdb':
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
        elif stmt.name == '.':
            self.lprint(repr(self.ptr))
        elif stmt.name == '..':
            if self.stack:
                self.ptr, self.ptrname = self.stack.pop()
            self.set_prompt(self.ptrname)
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
                                    self.lprint(line, end='')
                                else:
                                    self.lprint(repr(line))
                        else:
                            self.lprint(ret, end='')
                        return
                    elif isinstance(ret, (bool, basestring, int, float)):
                        self.lprint(ret, end='')
                        return
                    else:
                        return
                except:
                    self.showtraceback()
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
                self.pprint(obj)
            else:
                self.stack.append((self.ptr, self.ptrname))
                self.ptr = obj
                if hasattr(obj, 'key_repr'):
                    self.ptrname = obj.key_repr()
                else:
                    self.ptrname = stmt.name
                self.set_prompt(self.ptrname)
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
                    self.showtraceback()
        finally:
            if not rcode:
                for _ in range(rcounter):
                    self.ptr, self.ptrname = self.stack.pop()
                    self.set_prompt(self.ptrname)
        return indent

    def loadrc(self, fname):
        with open(fname, 'r') as f:
            indent = 0
            for line in f.readlines():
                try:
                    parser = Parser(line)
                except:
                    self.showtraceback()
                    continue
                for sentence in parser.sentences:
                    indent = self.handle_sentence(sentence, indent)

    def interact(self, readfunc=None):

        if self.isatty and readfunc is None:
            self.lprint("pyroute2 cli prototype")

        if readfunc is None:
            readfunc = self.raw_input

        indent = 0
        while True:
            try:
                text = readfunc(self.prompt)
            except EOFError:
                if self.stack:
                    self.lprint()
                    self.ptr, self.ptrname = self.stack.pop()
                    self.set_prompt(self.ptrname)
                    continue
                else:
                    self.close()
                    break
            except Exception:
                self.close()
                break

            try:
                parser = Parser(text)
            except:
                self.showtraceback()
                continue
            for sentence in parser.sentences:
                indent = self.handle_sentence(sentence, indent)

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
