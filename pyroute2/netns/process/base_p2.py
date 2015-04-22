from pyroute2.netns.process import MetaPopen


class NSPopenBase(object):

    __metaclass__ = MetaPopen
