import re
import shlex
from pyroute2.common import basestring
from pyroute2.cli import (t_stmt,
                          t_dict,
                          t_comma,
                          t_end_of_dict,
                          t_end_of_sentence,
                          t_end_of_stream)


class Token(object):

    def __init__(self, lex, expect=tuple(), prohibit=tuple(), leaf=False):
        self.lex = lex
        self.leaf = leaf
        self.kind = 0
        self.name = None
        self.argv = []
        self.kwarg = {}
        self.parse()
        if expect and self.kind not in expect:
            raise SyntaxError('expected %s, got %s' % (expect, self.kind))
        if prohibit and self.kind in prohibit:
            raise SyntaxError('unexpected %s' % (self.name, ))

    def convert(self, arg):
        if re.match('^[0-9]+$', arg):
            return int(arg)
        else:
            return arg

    def parse(self):
        # triage
        first = self.lex.get_token()
        self.name = first

        ##
        # no token
        #
        if first == '':
            self.kind = t_end_of_stream

        ##
        # dict, e.g. {ifname eth0, target localhost}
        #
        elif first == '{':
            while True:
                nt = Token(self.lex, expect=(t_stmt,
                                             t_comma,
                                             t_end_of_dict))
                if nt.kind == t_stmt:
                    if len(nt.argv) < 1:
                        raise SyntaxError('value expected')
                    elif len(nt.argv) == 1:
                        self.kwarg[nt.name] = nt.argv[0]
                    else:
                        self.kwarg[nt.name] = nt.argv
                elif nt.kind == t_end_of_dict:
                    self.kind = t_dict
                    self.name = '%s' % (self.kwarg)
                    return

        ##
        # end of dict
        #
        elif first == '}':
            self.kind = t_end_of_dict

        ##
        # end of sentence
        #
        elif first == ';':
            self.kind = t_end_of_sentence

        ##
        # end of dict entry
        #
        elif first == ',':
            self.kind = t_comma

        ##
        # simple statement
        #
        # object name::
        #   interfaces;
        #
        # function call::
        #   commit
        #   add {ifname test0, kind dummy}
        #   add test0 dummy
        #
        # locator key/value::
        #   {ifname eth0,
        #    target localhost}
        #
        else:
            self.name = first
            self.kind = t_stmt
            while not self.leaf:
                nt = Token(self.lex,
                           leaf=True,
                           expect=(t_comma,
                                   t_end_of_dict,
                                   t_end_of_stream,
                                   t_end_of_sentence,
                                   t_stmt,
                                   t_dict))
                if nt.kind == t_dict:
                    self.kwarg = nt.kwarg
                elif nt.kind == t_stmt:
                    self.argv.append(self.convert(nt.name))
                else:
                    self.lex.push_token(nt.name)
                    return


class Sentence(object):

    def __init__(self, text, indent=0, master=None):
        self.statements = []
        self.lex = shlex.shlex(text)
        self.lex.wordchars += '.:/'
        self.lex.commenters = '#!'
        self.lex.debug = False
        self.indent = indent
        if master:
            self.chain = master.chain
        else:
            self.chain = []
            self.parse()

    def parse(self):
        sentence = self
        while True:
            nt = Token(self.lex)
            if nt.kind == t_end_of_sentence:
                sentence = Sentence(None, self.indent, master=self)
            elif nt.kind == t_end_of_stream:
                return
            else:
                sentence.statements.append(nt)
            if sentence not in self.chain:
                self.chain.append(sentence)

    def __repr__(self):
        ret = '----\n'
        for s in self.statements:
            ret += '%i [%s] %s\n' % (self.indent, s.kind, s.name)
            ret += '\targv: %s\n' % (s.argv)
            ret += '\tkwarg: %s\n' % (s.kwarg)
        return ret


class Parser(object):

    def __init__(self, stream):
        self.stream = stream
        self.indent = None
        self.sentences = []
        self.parse()

    def parse(self):
        if hasattr(self.stream, 'readlines'):
            for text in self.stream.readlines():
                self.parse_string(text)
        elif isinstance(self.stream, basestring):
            self.parse_string(self.stream)
        else:
            raise ValueError('unsupported stream')
        self.parsed = True

    def parse_string(self, text):
        # 1. get indentation
        indent = re.match(r'^([ \t]*)', text).groups(0)[0]
        spaces = []
        # 2. sort it
        if indent:
            spaces = list(set(indent))
            if len(spaces) > 1:
                raise SyntaxError('mixed indentation')
            if self.indent is None:
                self.indent = spaces[0]
            if self.indent != spaces[0]:
                raise SyntaxError('mixed indentation')
        sentence = Sentence(text, len(indent))
        self.sentences.extend(sentence.chain)
