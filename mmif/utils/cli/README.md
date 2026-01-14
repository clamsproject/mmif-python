# MMIF CLI Scripts

This directory contains CLI scripts like `source` and `rewind` that can be called from the command line. These scripts are called as subcommands of the `mmif` CLI script, for example `mmif source --help`.


## Adding another CLI script

To add a CLI script all you need to do is add a python module to `mmif/utils/cli` and make sure it has the following three methods:

1. `prep_argparser(**kwargs)` to define and return an instance of `argparse.ArgumentParser`.

2. `describe_argparser()` to return a pair of strings that describe the script. The first string is a one-line description of the argument parser and the second a more verbose description. These will be shown for `mmif --help` and `mmif subcommand --help` respectively.

3. `main(args)` to do the actual work of running the code

See the current CLI scripts for examples.


## Some background

The mmif-python package has a particular way to deal with CLI utility scripts. All scripts live in the mmif.utils.cli package. The `mmif/__init__.py` module has the `cli()` function which illustrates the requirements on utility scripts:

```python
def cli():
    parser, subparsers = prep_argparser_and_subcmds()
    cli_modules = {}
    for cli_module in find_all_modules('mmif.utils.cli'):
        cli_module_name = cli_module.__name__.rsplit('.')[-1]
        cli_modules[cli_module_name] = cli_module
        subcmd_parser = cli_module.prep_argparser(add_help=False)
        subparsers.add_parser(cli_module_name, parents=[subcmd_parser],
                              help=cli_module.describe_argparser()[0],
                              description=cli_module.describe_argparser()[1],
                              formatter_class=argparse.RawDescriptionHelpFormatter)
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    if args.subcmd not in cli_modules:
        parser.print_help(sys.stderr)
    else:
        cli_modules[args.subcmd].main(args)
```

<!--
[cli() function](https://github.com/clamsproject/mmif-python/blob/8e6426d8d4345485fff06a0a149657e3d4fc8399/mmif/__init__.py#L47-L66)
-->

You can see the invocations of the three functions mentioned above.

The `prep_argparser()` function uses `find_all_modules()`, which finds modules in the top-level of the cli package. That module could have all the code needed for the CLI to work, but it could refer to other modules as well. For example, the `summary.py` script is in `cli`, but it imports the summary utility from `mmif.utls`.

In the setup.py script there is this passage towards the end of the file:

```python
    entry_points={
        'console_scripts': [
            'mmif = mmif.__init__:cli',
        ],
    },
```

This leaves it up to the `cli()` method to find the scripts and this is why just adding a submodule as mentioned above works. Note that the initialization file of the cli package imports two of the commandline related scripts:

```python
from mmif.utils.cli import rewind
from mmif.utils.cli import source
```

These may be used somewhere, but they are not necessary to run MMIF CLI scripts.

