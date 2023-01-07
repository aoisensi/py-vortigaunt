import sys
from argparse import ArgumentParser

from convert import _convert

parser = ArgumentParser()

parser.add_argument("-S", "--scale", default=2.0)
parser.add_argument("names", metavar="NAME", type=str,
                    nargs="+", help="mdl file name")


def main():
    if 'FbxCommon' not in sys.modules:
        raise Exception('fbx sdk is not found. please install manualy.')

    args = parser.parse_args()
    for filename in args.names:
        try:
            _convert(filename)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    main()
