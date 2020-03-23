#!/usr/bin/env python
import os
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

# When one runs pip install from the git repo, the setup.ini
# doesn't exist. But we still have here a full git repo with
# all the git log and with the Makefile.
#
# So just try to use it.
try:
    os.stat('setup.ini')
except:
    os.system('make force-version')
config = configparser.ConfigParser()
config.read('setup.ini')

module = __import__(config.get('setup', 'setuplib'),
                    globals(),
                    locals(),
                    ['setup'], 0)
setup = getattr(module, 'setup')

readme = open("README.md", "r")


setup(name='pyroute2',
      version=config.get('setup', 'release'),
      description='Python Netlink library',
      author='Peter V. Saveliev',
      author_email='peter@svinota.eu',
      url='https://github.com/svinota/pyroute2',
      license='dual license GPLv2+ and Apache v2',
      packages=['pyroute2',
                'pyroute2.bsd',
                'pyroute2.bsd.rtmsocket',
                'pyroute2.bsd.pf_route',
                'pyroute2.cli',
                'pyroute2.config',
                'pyroute2.dhcp',
                'pyroute2.ipdb',
                'pyroute2.iproute',
                'pyroute2.ndb',
                'pyroute2.ndb.objects',
                'pyroute2.netns',
                'pyroute2.netns.process',
                'pyroute2.inotify',
                'pyroute2.ethtool',
                'pyroute2.netlink',
                'pyroute2.netlink.generic',
                'pyroute2.netlink.ipq',
                'pyroute2.netlink.nfnetlink',
                'pyroute2.netlink.rtnl',
                'pyroute2.netlink.rtnl.ifinfmsg',
                'pyroute2.netlink.rtnl.ifinfmsg.plugins',
                'pyroute2.netlink.rtnl.tcmsg',
                'pyroute2.netlink.taskstats',
                'pyroute2.netlink.nl80211',
                'pyroute2.netlink.devlink',
                'pyroute2.netlink.diag',
                'pyroute2.netlink.event',
                'pyroute2.nftables',
                'pyroute2.protocols',
                'pyroute2.remote'],
      scripts=['./cli/ss2',
               './cli/pyroute2-cli'],
      install_requires=['win_inet_pton ; platform_system=="Windows"', ],
      extras_require={'ss2': ['psutil~=5.0']},
      classifiers=['License :: OSI Approved :: GNU General Public ' +
                   'License v2 or later (GPLv2+)',
                   'License :: OSI Approved :: Apache Software License',
                   'Programming Language :: Python',
                   'Topic :: Software Development :: Libraries :: ' +
                   'Python Modules',
                   'Topic :: System :: Networking',
                   'Topic :: System :: Systems Administration',
                   'Operating System :: POSIX :: Linux',
                   'Intended Audience :: Developers',
                   'Intended Audience :: System Administrators',
                   'Intended Audience :: Telecommunications Industry',
                   'Programming Language :: Python :: 2.6',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3',
                   'Development Status :: 4 - Beta'],
      long_description=readme.read())
