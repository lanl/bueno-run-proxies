# bueno-run-proxies | SNAP

<br/>

## Quick Start:

Execute the bueno run script with the default configuration parameters and
assumed build location of LANL's SN Proxy Application (SNAP) with no
container.
```Shell
$ bueno run -a none -p bueno_snap.py
```

<br/>

## Config File:
Within the experiments directory there is a configuration file for this bueno
run script. Configuration settings include input and output files for SNAP,
name, description and experiment executable. Also customisable in this file
is the iterative run commands controls. Listed in the file as "runcmds", the
first two items define the inclusive range of numbers to be tested. The second,
is the command being passed to the terminal with the variable numerical value 
established in the previous range of numbers. The final item in the config file
is the additional parameter for SNAP's input and output file.

```
# Custom bueno runscript for SN Application Proxy (SNAP).
# --csv-output data.csv
# --description 'bueno run script for SNAP.'
# --executable '~/SNAP_build/src/gsnap'
# --input './experiments/config'
# --name 'snap'
# --runcmds "4, 10, 'mpiexec -n %n', 'nidx'"
{} ./experiments/input ./experiments/output
```

> Note:
> --input is the bueno run script input and not to be confused with SNAP's
> input file; which is specified in the final line with ./experiments/input

<br/>

## Custom Configuration:
Modifications to the bueno run script should be defined in the above config
file rather than directly in bueno_snap.py. While the settings are mirrored
in the run script, the input file is consulted at run time and the defaults are
overridden with the parameters found in experiments/config.

There are some additional options for acquiring the timing table from the SNAP
output file. In the event that the size/format of SNAP's data table is modified
in future, the run script can easily be tweaked to read more or less lines when
gathering metadata.

```Python
# snap output table variables
SO_OFFSET = 5
SO_WIDTH = 15

# used later in the parse_snapfile def:
start = table_pos + SO_OFFSET
end = table_pos + SO_OFFSET + SO_WIDTH
time_table = lines[start:end]  # isolate table lines
```

<br/>

## Script Execution:

```Shell
# Generic, non-containerized application
$ bueno run -a none -p bueno_snap.py

# With containerized application
$ bueno run -i ~/bueno-proxies-src/snap/test-snap.tar.gz -p bueno_snap.py
```

After execution, the metadata files are stored in the new local snap folder.
The one created by the custom post action is called: timing-metadata.yaml.
Additionally, the generated report is saved as: data.csv in the same
directory.

<br/>

### Los Alamos National Laboratory Code Release
C19133 [bueno](https://github.com/lanl/bueno)

<br/>

-------------------------------------------------------------------------------
Last Modified - 12/1/2020
