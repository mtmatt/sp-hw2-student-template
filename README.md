# sp-hw2-student-template

Start your submission here. The staff release workflow adds the public
`student-selftest/` bundle after it has built and verified the release tools.
It contains public diagnostic cases and a disposable self-test keypair; it
does not contain staff grading keys or private tests.

## Run the public self-test

Verified release targets are Linux x86_64 and Apple-silicon macOS
(`darwin-arm64`). From the repository root, create the bundled service
environment with an explicit CPython 3.14 interpreter, then run the launcher:

```sh
./student-selftest/bootstrap-python.sh /path/to/python3.14
./student-selftest/run-selftest.sh [submission-dir] [relative-student-program]
```

The defaults are the current directory and `sp`. The displayed result is a
local diagnostic score. Official grading combines the public and private plans
at 30% and 70%, respectively.
