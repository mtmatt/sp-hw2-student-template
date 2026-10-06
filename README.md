# sp-hw2-student-template

Write your program in `sp.c`. You may split it into more sources and headers.

## Build

```sh
make        # builds ./sp
make clean  # removes it
```

If you add files, update the `sp` rule in the `Makefile` to build them, and
list them in `SUBMISSION_FILES`:

```make
SUBMISSION_FILES = sp.c node.c node.h
```

The `Makefile` is always submitted, so it need not be listed.

## Test

```sh
make test
```

builds `sp` so compile errors show first, then grades your program on the
public tests in `tests/public`. The judge builds and runs only the files
`make submission` would pack, copied into a temporary directory, so a file
missing from `SUBMISSION_FILES` fails here too.

While the dashboard is shown, your program's stderr is hidden. To see it in
the terminal, send the report to a file instead:

```sh
make test > report.txt
```

## Submit

```sh
make submission STUDENT_ID=b12902033
```

creates `b12902033.zip` holding a `b12902033/` directory with the `Makefile`
and every file in `SUBMISSION_FILES`. You can instead set `STUDENT_ID` once
in the `Makefile`. Upload the zip to NTU COOL.
