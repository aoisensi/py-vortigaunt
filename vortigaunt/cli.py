import sys
from argparse import ArgumentParser
from traceback import format_exc

from vortigaunt.convert import _convert


parser = ArgumentParser()

parser.add_argument("-S", "--scale", default=2.0)
parser.add_argument("names", metavar="NAME", type=str,
                    nargs="+", help="mdl file name")
parser.add_argument("--ascii", action='store_true')

args = parser.parse_args()


def main():
    if 'FbxCommon' not in sys.modules:
        raise Exception('fbx sdk is not found. please install manualy.')

    for filename in args.names:
        try:
            _convert(filename, args)
        except Exception:
            print(format_exc())


if __name__ == "__main__":
    main()
