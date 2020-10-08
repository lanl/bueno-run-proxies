# bueno_snap.py

## Customization:
There are a few notable customization options available depending on which
dependencies were used to build SNAP. Chief of which is the path to the active
installation of SNAP. There are also options for which input and output files
will be used by SNAP.

```Python
# snap path variables
GSNAP = '~/SNAP_build/src/gsnap'
S_IN = './experiments/input'
S_OUT = './experiments/output'
```

Additionally, there are some options for acquiring the timing table from the
output file. In the event that the size of the table is modified in future,
the run script can easily be tweaked to read more or less lines when
gathering metadata.

```Python
# snap output file variables
SO_OFFSET = 5
SO_WIDTH = 15

# used later in the code:
start = table_pos + SO_OFFSET
end = table_pos + SO_OFFSET + SO_WIDTH
time_table = lines[start:end]  # isolate table lines
```

## Execute:
```Shell
bueno run -a none -p bueno_snap.py 
```
After execution, the metadata files are stored in the local snap-test folder.
The one created by the custom post action is called: timing-metadata.