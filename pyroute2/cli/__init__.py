from __future__ import print_function

import re
import sys
import code
import shlex
import socket
import getpass
from pprint import pprint
from pyroute2 import IPDB
from pyroute2.common import basestring
from pyroute2.ipdb.transactional import Transactional
from pyroute2.ipdb.interfaces import Interface
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
        self.ipdb = IPDB()
        self.ptr = self.ipdb
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
            if isinstance(self.ptr, Interface):
                self.prompt = 'if : %s > ' % (self.ptr.ifname)
            elif prompt is not None:
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

    def interact(self, readfunc=None):

        if readfunc is None:
            readfunc = self.raw_input

        if self.isatty:
            self.lprint("IPDB cli prototype")
        while True:
            try:
                cmd = readfunc(self.prompt)
            except:
                self.lprint()
                break

            # strip comments
            fbang = cmd.find('!')
            fhash = cmd.find('#')
            if fbang >= 0:
                cmd = cmd[:fbang]
            if cmd.find('#') >= 0:
                cmd = cmd[:fhash]

            # skip empty strings
            if not len(cmd.strip()):
                continue

            # calculate leading whitespaces
            lcmd = cmd.lstrip()
            lspaces = len(cmd) - len(lcmd)
            # strip all whitespaces
            cmd = cmd.strip()

            # compare spaces with self.ptr
            if not self.isatty:
                while self.stack and self.stack[-1][2] >= lspaces:
                    # pop stack
                    self.ptr, self.ptrname, spaces = self.stack.pop()
                    # compare spaces
                    if spaces == lspaces:
                        break
                    elif spaces < lspaces:
                        self.lprint('indentation warning: <%s>' % cmd)
                        break
                self.set_prompt(self.ptrname)

            if not cmd:
                continue
            elif cmd == 'debug':
                if HAS_PDB:
                    pdb.set_trace()
                else:
                    self.lprint("pdb is not available")
            elif cmd == 'exit':
                break
            elif cmd == 'ls':
                self.lprint(dir(self.ptr))
            elif cmd == 'help':
                self.help()
            elif cmd == '.':
                self.lprint(repr(self.ptr))
            elif cmd in ('..', ';'):
                if self.stack:
                    self.ptr, self.ptrname, lspaces = self.stack.pop()
                self.set_prompt(self.ptrname)
            else:
                # parse the command line into tokens
                #
                # symbols .:/ etc. are needed to represent IP addresses
                # as whole tokens
                #
                # quotes should be stripped
                #
                parser = shlex.shlex(cmd)
                parser.wordchars += '.:/-+*'
                pre_tokens = list(parser)
                tokens = []
                for token in pre_tokens:
                    if token[0] == token[-1] and token[0] in ("\"'"):
                        tokens.append(token[1:-1])
                    else:
                        tokens.append(token)

                # an attribute
                obj = getattr(self.ptr, tokens[0], None)
                if obj is None:
                    # try a kay
                    try:
                        obj = self.ptr[self.convert(cmd)]
                    except Exception:
                        self.lprint('object not found')
                        continue
                if hasattr(obj, '__call__'):
                    argv = []
                    kwarg = {}
                    length = len(tokens)
                    x = 1
                    while x < len(tokens):
                        # is it a kwarg?
                        if x < length - 2 and tokens[x + 1] == '=':
                            kwarg[tokens[x]] = self.convert(tokens[x + 2])
                            x += 3
                        else:
                            argv.append(self.convert(tokens[x]))
                            x += 1
                    try:
                        ret = obj(*argv, **kwarg)
                        if ret and not isinstance(ret, (Transactional, IPDB)):
                            self.pprint(ret)
                    except:
                        self.showtraceback()
                else:
                    if isinstance(obj, (basestring, int, float)):
                        # is it a simple attribute?
                        if isinstance(self.ptr, Transactional) and \
                                len(tokens) > 1:
                            # set it
                            self.ptr[tokens[0]] = self.convert(tokens[1])
                        else:
                            # or print it
                            self.pprint(self.ptr[tokens[0]])
                    else:
                        # otherwise change the context
                        self.stack.append((self.ptr, self.ptrname, lspaces))
                        self.ptr = obj
                        self.ptrname = tokens[0]
                        self.set_prompt(tokens[0])

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
