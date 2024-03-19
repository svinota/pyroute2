import argparse

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument(
    '-c', '--cls', help='message class to use for decoding the data'
)
argument_parser.add_argument('-d', '--data', help='data dump file')
argument_parser.add_argument(
    '-f', '--format', default='hex', help='data file format: hex, pcap'
)
argument_parser.add_argument(
    '-m', '--match', help='match protocol family (only for pcap data)'
)
args = argument_parser.parse_args()
__all__ = [args]
