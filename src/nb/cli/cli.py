#!/usr/bin/env python
# -*- python -*-

"""
Juyter notebook command wrapper

Start jupyter lab or notebook with the current python executable as the kernel.

AUTHOR: Daisuke Arai
"""

import os
import sys
import argparse
import random
import hashlib
import time
from shutil import which
from contextlib import suppress
from pathlib import Path
from shutil import rmtree


KEY_JUPYTER_DATA_DIR = 'JUPYTER_DATA_DIR'

def print_error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def is_project_root_dir(x):
    return x.parent if x.is_dir() else None

def is_project_root_file(x):
    return x.parent if x.is_file() else None

ROOT_SPECS = {
    '.git': is_project_root_dir,
    'pyproject.toml': is_project_root_file,
}

def make_password(plain_password):
    salt_len = 12  # notebook.auth.salt_len
    h = hashlib.new('sha1')
    salt = f"{random.getrandbits(4 * salt_len):0{salt_len}x}"
    h.update(plain_password.encode('utf-8') + salt.encode('ascii'))
    password = ':'.join(('sha1', salt, h.hexdigest()))
    return password

def find_project_root_recurse(d, find_root):
    rel = d.relative_to(find_root)  # raise ValueError if d outside find_root
    if str(rel) == '.':
        return None
    for item in d.iterdir():
        spec = ROOT_SPECS.get(item.name)
        if spec:
            found = spec(item)
            if found:
                return found
    try:
        return find_project_root_recurse(d.parent, find_root)
    except ValueError:
        return None

def find_project_root(directory='.'):
    d = Path(directory).resolve()
    root = Path('~').expanduser()
    try:
        d.relative_to(root)
    except ValueError:
        root = Path('/')
    return find_project_root_recurse(Path(directory).resolve(), root)

def main():

    parser = argparse.ArgumentParser(
        prog='Jupyter Notebook Wrapper',
        description='Run jupyter lab or notebook')

    parser.add_argument('--ip')
    parser.add_argument('--nb-verbose', action='store_true')
    parser.add_argument('--only-update-kernel', action='store_true')
    parser.add_argument('-N', '--no-password', action='store_true')
    parser.add_argument('--notebook', action='store_true')
    parser.add_argument('--python')
    parser.add_argument('-p', '--password')
    args, rest_of_args = parser.parse_known_args()
    sys.argv = [ sys.executable ] + rest_of_args
    
    python_executable = args.python or which('python3') or sys.executable

    # get jupyter data directory
    jupyter_data_dir = os.environ.get(KEY_JUPYTER_DATA_DIR, '')
    if jupyter_data_dir == '':
        jupyter_data_dir = Path('~/.local/share/jupyter').expanduser()

    # find project root
    root = find_project_root()

    # Kernel spec directory
    kernel_name = 'default' if root is None else root.name
    kernel_path = Path(jupyter_data_dir) / 'kernels' / kernel_name
    os.environ[KEY_JUPYTER_DATA_DIR] = str(Path(jupyter_data_dir).absolute())

    if args.nb_verbose:
        print_error(f'Target python executable is {python_executable}')
        print_error(f'Target kernel path is {kernel_path}')

    # Re-install kernel
    try:
        import ipykernel.kernelspec
    except ImportError:
        print_error('\n\n***WARNING***\n\tipykernel is not installed. please run pip install ipykernel\n\n')
        time.sleep(2)
    else:
        with suppress(FileNotFoundError):
            rmtree(kernel_path)
        kernel_path.parent.mkdir(parents=True, exist_ok=True)
        overrides = {
            "display_name": kernel_name,
        }
        old_executable = sys.executable
        try:
            sys.executable = python_executable
            ipykernel.kernelspec.write_kernel_spec(path=str(kernel_path), overrides=overrides)
        finally:
            sys.executable = old_executable

    if args.ip is not None:
        sys.argv += [ '--NotebookApp.ip', args.ip ]
    else:
        # change default listen address to 127.0.0.1 for avoid HSTS
        sys.argv += [ '--NotebookApp.ip', '127.0.0.1' ]

    # check jupyterlab is installed
    if not args.notebook:
        try:
            from jupyterlab.labapp import main as labapp_main
        except ImportError:
            args.notebook = True
            pass

    if args.only_update_kernel:
        return

    if not args.notebook and args.no_password:
        # password_required=False does not work for Jupyter lab.
        args.password = ""  # Use an encrypted blank password instead.

    if args.password is not None:
        sys.argv += [ "--NotebookApp.password", make_password(args.password) ]
    else:
        sys.argv += [ "--NotebookApp.password", "" ]

    if args.no_password:
        sys.argv += [ "--NotebookApp.token", "" ]
        sys.argv += [ "--NotebookApp.password_required", "False" ]

    if args.notebook:
        try:
            from jupyter_core.command import main
        except ImportError:
            print_error('Please install notebook or jupyterlab')
            sys.exit(1)
        else:
            sys.argv = [sys.executable, 'notebook'] + sys.argv[1:]
            main()
    else:
        sys.argv += [ '--MultiKernelManager.default_kernel_name', kernel_name ]
        labapp_main(argv=sys.argv[1:])


if __name__ == '__main__':
    main()
