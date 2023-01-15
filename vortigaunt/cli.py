from argparse import ArgumentParser

from rich.console import Console
from rich_argparse import RichHelpFormatter

from convert import convert

parser = ArgumentParser(formatter_class=RichHelpFormatter)

parser.add_argument("-S", "--scale", default=0.02)
parser.add_argument("names", metavar="NAME", type=str,
                    nargs="+", help="mdl file name")
parser.add_argument("--ascii", action='store_true')
args = parser.parse_args()

console = Console()


def main():
    for filename in args.names:
        try:
            convert(filename, args, console)
        except Exception:
            console.print_exception()


if __name__ == "__main__":
    main()
