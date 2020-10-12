# bueno_snap.py

## Defaults:
There are several defaults established in main portion of the run script.
These include, the description of the experiment being performed, the path to
the SNAP instance, SNAP's input and output file destinations, as well as the
destination of the bueno csv report file.
```Python
# Default values
defaults = dict()
defaults['name'] = 'SNAP'
defaults['description'] = desc
defaults['executable'] = '~/SNAP_build/src/gsnap'
defaults['input'] = './experiments/input'
defaults['output'] = './output'
defaults['csv'] = './data.csv'
```

Additionally, there are some options for acquiring the timing table from the
output file. In the event that the size of the table is modified in future,
the run script can easily be tweaked to read more or less lines when
gathering metadata.

```Python
# snap output file variables
SO_OFFSET = 5
SO_WIDTH = 15

# used later in the parse_snapfile def:
start = table_pos + SO_OFFSET
end = table_pos + SO_OFFSET + SO_WIDTH
time_table = lines[start:end]  # isolate table lines
```

## Execute:
```Shell
bueno run -a none -p bueno_snap.py 
```
After execution, the metadata files are stored in the local snap-test folder.
The one created by the custom post action is called: "timing-metadata.yaml".
Additionally, the generated report is saved as: "data.csv" in the same
directory.