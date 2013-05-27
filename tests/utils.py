import subprocess


def get_ip_addr(interface=None):
    argv = ['ip', '-o', 'ad']
    if interface:
        argv.extend(['li', 'dev', interface])
    out = subprocess.check_output(argv).split('\n')
    ret = []
    for string in out:
        fields = string.split()
        if len(fields) >= 5 and fields[2][:4] == 'inet':
            ret.append(fields[3])
    return ret


def get_ip_link():
    ret = []
    out = subprocess.check_output(['ip', '-o', 'li']).split('\n')
    for string in out:
        fields = string.split()
        if len(fields) >= 2:
            ret.append([fields[1][:-1]])
    return ret


def get_ip_route():
    ret = []
    out = subprocess.check_output(['ip',
                                   '-4',
                                   'ro',
                                   'li',
                                   'ta',
                                   '255']).split('\n')
    for string in out:
        if len(string):
            ret.append(string)
    return ret
