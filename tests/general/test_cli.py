import io
import os
import sys
import re
import threading
import subprocess
import json
import collections
import imp
from concurrent import futures
from pyroute2 import Console
from pyroute2 import IPDB
from utils import require_user
from nose.plugins.skip import SkipTest
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

TMPDIR = os.environ.get('TMPDIR', '.')
scripts = {}
try:
    os.chdir('examples/cli')
except:
    raise SkipTest('test scripts not found')

for name in os.listdir('.'):
    with open(name, 'r') as f:
        scripts[name] = f.read()
os.chdir('../..')


class TestBasic(object):

    def readfunc(self, prompt):
        ret = self.queue.get()
        if ret is None:
            raise Exception("EOF")
        else:
            return ret

    def setup(self):
        self.ipdb = IPDB()
        if sys.version_info[0] == 2:
            self.io = io.BytesIO()
        else:
            self.io = io.StringIO()
        self.queue = Queue()
        self.con = Console(stdout=self.io)
        self.con.isatty = False
        self.thread = threading.Thread(target=self.con.interact,
                                       args=[self.readfunc, ])
        self.thread.start()

    def feed(self, script):
        for line in script.split("\n"):
            self.queue.put(line)
        self.queue.put(None)
        self.thread.join()
        self.io.flush()

    def teardown(self):
        self.ipdb.release()
        self.con.close()

    # 8<---------------- test routines ------------------------------

    def test_dump_lo(self):
        self.feed(scripts['test_dump_lo'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:00:00:00:00:00'
        assert ('127.0.0.1', 8) in interface['ipaddr']

    def test_ensure(self):
        require_user('root')
        self.feed(scripts['test_ensure'])
        assert 'test01' in self.ipdb.interfaces
        assert ('172.16.189.5', 24) in self.ipdb.interfaces.test01.ipaddr
        self.ipdb.interfaces.test01.remove().commit()

    def test_comments_bang(self):
        require_user('root')
        self.feed(scripts['test_comments_bang'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'

    def test_comments_hash(self):
        require_user('root')
        self.feed(scripts['test_comments_hash'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'

    def test_comments_mixed(self):
        require_user('root')
        self.feed(scripts['test_comments_mixed'])
        interface = eval(self.io.getvalue())
        assert interface['address'] == '00:11:22:33:44:55'
        assert interface['ifname'] == 'test01'


class TestPopen(TestBasic):

    def setup(self):
        self.ipdb = IPDB()
        self.io = io.BytesIO()
        self.con = subprocess.Popen(['python', '%s/bin/ipdb' % TMPDIR],
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

    def teardown(self):
        self.ipdb.release()

    def feed(self, script):
        out, err = self.con.communicate(script.encode('ascii'))
        self.io.write(out)
        self.con.wait()


class TestTools(object):
    class Utils:
        @staticmethod
        def which(executable, fail=False):
            def is_executable(filename):
                return (os.path.isfile(filename) and
                        os.access(filename, os.X_OK))

            pathname, filename = os.path.split(executable)
            if pathname:
                if is_executable(executable):
                    return executable
            else:
                for path in [i.strip('""')
                             for i in
                             os.environ["PATH"].split(os.pathsep)]:
                    filename = os.path.join(path, executable)
                    if is_executable(filename):
                        return filename

            if fail:
                raise RuntimeError("No %s binary found in PATH." % executable)

    class OsActor:
        @staticmethod
        def run_cli(cmd, *args):

            opts = ' '.join(args)

            p_exec = subprocess.Popen("%s %s" % (cmd, opts),
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      shell=True)
            out, err = p_exec.communicate()

            if p_exec.returncode != 0:
                raise RuntimeError("cli call failed: %s" % (err))

            return out

    class FlowParser:
        # flows patterns
        flow_types = ['tcp', 'raw', 'udp', 'dccp']
        flow_decolate_re = re.compile(r"(%s)" % ("|".join(flow_types)))

        ip_v4_addr_sub_re = r"([0-9]{1,3}\.){3}[0-9]{1,3}(:\d+)"
        # ref.: to commented, untinkered version: ISBN 978-0-596-52068-7
        ip_v6_addr_sub_re = r"(?:(?:[A-F0-9]{1,4}:){7}[A-F0-9]{1,4}|"\
                            r"(?=(?:[A-F0-9]{0,4}:){0,7}[A-F0-9]{0,4})"\
                            r"(([0-9A-F]{1,4}:){1,7}|:)((:[0-9A-F]{1,4})"\
                            r"{1,7}|:))(:\d+)"

        pid_re = re.compile(r"pid=(?P<pid>\d+)", re.MULTILINE)
        ip_v4_endp_re = re.compile(r"" + r"(?P<src_ep>" +
                                   ip_v4_addr_sub_re + ")" +
                                   r"\s+" + r"(?P<dst_ep>" +
                                   ip_v4_addr_sub_re + ")")
        ip_v6_endp_re = re.compile(r"" + r"(?P<src_ep>" +
                                   ip_v6_addr_sub_re + ")" +
                                   r"\s+" + r"(?P<dst_ep>" +
                                   ip_v6_addr_sub_re + ")",
                                   re.IGNORECASE)

        def _dissect_ep(self, whole):
            shards = whole.split(":")
            addr = None
            # cure by checking ip_version
            if len(shards) > 2:
                addr = ":".join(shards[:-1])
            else:
                addr = ".".join(shards[:-1])

            port = shards[-1]

            return addr, port

        def parse_flow(self, matter):
            # matter = matter.strip()
            fl_end_p = self.ip_v4_endp_re.search(matter)
            if None is fl_end_p:
                fl_end_p = self.ip_v6_endp_re.search(matter)

            if None is fl_end_p:
                raise RuntimeError("Unexpected flows outline")

            src_addr, src_p = self._dissect_ep(fl_end_p.group('src_ep'))
            dst_addr, dst_p = self._dissect_ep(fl_end_p.group('dst_ep'))
            pid = self.pid_re.search(matter).group('pid')

            res = {"src": src_addr,
                   "src_port": int(src_p),
                   "dst": dst_addr,
                   "dst_port": int(dst_p),
                   "pid": pid}

            return res

    def setup(self):
        utils = TestTools.Utils
        self.ss_bin = utils.which('ss')

        ss2_script = './bin/ss2'
        self.ss2 = imp.load_source('ss2', ss2_script)

        if sys.version_info[0] == 2:
            import cStringIO
            self.stream_sink = cStringIO.StringIO()
        else:
            self.stream_sink = io.StringIO()

    def do_ss(self):
        parser = TestTools.FlowParser()
        actor = TestTools.OsActor
        flags = '-tu -n -p'
        tcp_flows_raw = str(actor.run_cli(self.ss_bin, flags))
        refined_flows = []

        tcp_flows_raw = parser.flow_decolate_re.split(tcp_flows_raw)

        # skip head
        tcp_flows_raw = tcp_flows_raw[1:]
        for _type, flow in zip(tcp_flows_raw[0::2], tcp_flows_raw[1::2]):
            if _type == 'tcp':
                refined_flow = parser.parse_flow(flow)
                refined_flows.append(refined_flow)

        return refined_flows

    def do_ss2(self):
        # emulate cli args
        args = collections.namedtuple('args', ['tcp', 'listen', 'all'])
        args.tcp = True
        args.listen = False
        args.all = False

        _stdout = sys.stdout
        sys.stdout = self.stream_sink

        self.ss2.run(args)

        # catch stdout
        sys.stdout = _stdout
        tcp_flows = self.stream_sink.getvalue()

        return json.loads(tcp_flows)

    def test_ss2(self):
        future_result_map = {}
        tcp_flows_hive = {}

        with futures.ThreadPoolExecutor(max_workers=100) as executor:

            future = executor.submit(self.do_ss)
            future_result_map[future] = 'ss'
            future = executor.submit(self.do_ss2)
            future_result_map[future] = 'ss2'

            done_iter = futures.as_completed(future_result_map)

            for future in done_iter:
                what = future_result_map[future]
                tcp_flows_hive[what] = future.result()

            ss_flows = tcp_flows_hive['ss']
            ss2_flows = tcp_flows_hive['ss2']['TCP']['flows']

            # might too stringent for parallelization approximation
            assert len(ss_flows) == len(ss2_flows)

            for f, _f in zip(ss_flows, ss2_flows):
                for k in ['src', 'dst', 'src_port', 'dst_port']:
                    assert f[k] == _f[k]
