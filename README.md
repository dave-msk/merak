# Merak

Merak is a package building toolkit.

This project is started as an attempt to implement a tool that builds a single Cython extension from a Python package, based on the discussion on StackOverflow - [Collapse multiple submodules to one Cython extension](https://stackoverflow.com/questions/30157363/collapse-multiple-submodules-to-one-cython-extension). See the **Idea** section below.

More features and functionalities may be added in the future.

## Install

To install the current release:

```sh
$ pip install merak
```

To upgrade Merak to the latest version, add `--upgrade` flag to the above command.

## Usage

Currently, Merak only supports the `cythonize` command for building binary externaion from a Python package. More features and functionalities may be added in the future.

To build a binary extension from a Python package:

```sh
$ merak cythonize PACKAGE_PATH OUTPUT_PATH
```

The package built will be placed at `<OUTPUT_PATH>/<PACKAGE_NAME>`. If `-f` is specified, any existing file / directory at this path will be overwritten.

```
usage: merak cythonize [-h] [-v] [-k] [-s SEP] [-f] path output

positional arguments:
  path               Python package path
  output             Output directory

optional arguments:
  -h, --help         show this help message and exit
  -v, --verbose      Log verbosity level. Default -> WARNING, -v -> INFO, -vv
                     or above -> DEBUG.
  -k, --color        Display logging messages in colors.
  -s SEP, --sep SEP  Module layer separator, must be Python identifier.
                     Defaults to '_'
  -f, --force        Force overwrite if target path exists
```

## Example

An example package `foo` is included in the `tests/` directory. It consists of one subpackage `bar` with a module `baz` containing a function `do()` in it.

To build the `foo` package, run the following command in the project root:

```sh
$ merak cythonize examples/foo foo-build
```

The `foo` binary package can then be found at `foo-build/foo`. Change directory to `foo-build` and use an interactive Python session to try it out:

```
>>> from foo.bar import baz
__main__:1: DeprecationWarning: Deprecated since Python 3.4. Use importlib.util.find_spec() instead.
>>> baz.do()
Running: foo.bar.baz.do()
```

The deprecation warning seems to originate from the import logic in the compiled `__init__` extension by Cython. It should cause no execution problems at all.

## Idea

Based on [this answer](https://stackoverflow.com/a/52714500/14927788), it appears that it is possible to build a single Cython extension with multiple modules included in it.

However, it does NOT work with multi-level packages. Cython builds a C source file for each module with an initializer named `PyInit_xxx`, which depends on the base name of the module. As the function is defined in the global scope, a name collision would happen if the same base name is used for different modules. For instance, the following package would have a name collision for `__init__.py` and `base.py`:

```
foo/
  __init__.py
  bar/
    __init__.py
    base.py
  baz/
    __init__.py
    base.py
```

Here, we solve the problem in two steps:

1. **Module Flattening:** We move all modules to the base layer, with name constructed from their original relative path: `path.replace(path_separator, sep)`, where `sep` is a legal Python identifier. For example, `foo/bar/base.py` -> `foo/bar_sep_base.py` if `sep="_sep_"`.
2. **Import Redirection:** We inject a finder inside the main `__init__.py` that redirects dotted-paths to their flattened counterparts. Using the above example, the finder redirects the import `foo.bar.base` to `foo.bar_sep_base`.

The injected finder is based on [this answer](https://stackoverflow.com/a/52729181/14927788) with some modifications. See the [template](./merak/data/__init__.tmpl) for implementation detail.

The result would contain a single `__init__` extension inside the package folder. The package folder is still required for the builtin importer to load it as a package, rather than a module. The above example would result in a `foo/` folder with a single `__init__` Cython extension in it.

## Resources

- [Cython.org](https://cython.org/)
- [Stackoverflow - Collapse multiple submodules to one Cython Extension](https://stackoverflow.com/questions/30157363/collapse-multiple-submodules-to-forone-cython-extension)

## License

[Apache License 2.0](./LICENSE)
