# bueno-run-proxies | SNAP

<br/>

## Quick Start:

Execute the bueno run script with the default configuration parameters and
assumed build location of LANL's SN Proxy Application
([SNAP](https://github.com/lanl/SNAP)).
```Shell
# Generic, non-containerized application
$ bueno run -a none -p bueno_snap.py

# With containerized application
$ bueno run -i /path/to/container/image.tar.gz -p bueno_snap.py
```

<br/>

## Experiment Configuration:

Experiment configuration can be modified in experiments/config. Settings
include input and output files for SNAP as well as the location of the SNAP
executable. Also customizable in this file are the iterative run commands.
The run commands define the inclusive range of numbers to be tested, the
format of the command being passed to the terminal. It's in this final item
that SNAP's input and output file is defined.
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

> ### Note: <br/>
> The --input flag is the bueno run script config file and not to be confused
> with SNAP's input file; which is specified in the final line with
> ./experiments/input <br/> <br/>
> If you change the destination of either of SNAP's files, the configuration
> flags will also need to be set/updated:
> <br/> # --snapinfile './experiments/new_input'
> <br/> # --snapoutfile './experiments/new_output'
> <br/> {} ./experiments/new_input ./experiments_new_output

<br/>

## Data Acquisition:

To reiterate, modifications to the bueno run script should be defined in the
above config file rather than directly in bueno_snap.py. While the settings
are mirrored in the run script, the input file is consulted at run time and
the defaults are overridden with the parameters found in experiments/config.

However, there are some additional options that can be modified that pertain
to acquiring the timing table from the SNAP output file. Should more or
alternative data found in SNAP's output file be the subject of interest, the
run script can easily be tweaked to read more or less lines when gathering
data.

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

## Post Analysis:

After execution, the metadata files are stored in the new directory, the name
of which is determined by the experiment name flag in config. Exploring within
each experiment result is saved in a time stamped and numbered directory. The
run script's post action creates several files containing information for post
analysis: timing-metadata.yaml and data.csv among them.

<br/>

### Los Alamos National Laboratory Code Release
C19133 [bueno](https://github.com/lanl/bueno)
