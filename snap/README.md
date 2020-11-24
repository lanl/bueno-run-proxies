# bueno-run-proxies | SNAP

## Defaults Parameters:
There are several defaults established in main portion of the run script.
These include, the name and description of the experiment being performed,
the path to the SNAP instance, SNAP's input and output file destinations,
the bueno input file, as well as the destination of the bueno csv report file
and the variable portions of the run commands. The first two items of the
run commands (runcmds) control the iterative portion of the script's
benchmarking proceedure; defining the range of inputs to be tested.

```Python
# Default values
defaults = experiment.CannedCLIConfiguration.Defaults
defaults.csv_output = './data.csv'
defaults.description = desc
defaults.executable = '~/SNAP_build/src/gsnap'
defaults.input = './experiments/input'
defaults.name = 'snap'
defaults.runcmds = (4, 4, 'mpiexec -n %n', 'nidx')
```

## Custom Configuration:
The default settings outlined above are mirrored in the config file found in
the experiment directory. Custom configurations should be defined here rather
than directly in the run script; the config file is consulted during runtime
and overwrites the default configuration if present.

> Note:
> 

Additionally, there are some options for acquiring the timing table from the
output file. In the event that the size of the table is modified in future,
the run script can easily be tweaked to read more or less lines when
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

## Script Execution:

Generic runscript execution, without an application container, follows the 
procedure outlined in the examples defined in the main readme document.
```Shell
bueno run -a none -p bueno_snap.py
```
After execution, the metadata files are stored in the new local snap folder.
The one created by the custom post action is called: timing-metadata.yaml.
Additionally, the generated report is saved as: data.csv in the same
directory.

If the intention is to run the containerized version of the application,
then the execute command changes slightly to include the tarball created in
the parallel bueno-proxies-src repository.

```Shell
bueno run -i ~/bueno-proxies-src/snap/test-snap.tar.gz -p bueno_snap.py
```

<br/>

### Los Alamos National Laboratory Code Release
C19133 [bueno](https://github.com/lanl/bueno)

<br/>

-------------------------------------------------------------------------------
Last Modified - 11/24/2020
