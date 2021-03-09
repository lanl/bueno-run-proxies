bueno-run-proxies | branson

<br/>

# Quick Start:

Execute the bueno run script with the default configuration parameters and
build location of [Branson](https://github.com/lanl/branson).
```Shell
# Generic, non-containerized application
$ bueno run -a none -p bueno_branson.py

# With containerized application
$ bueno run -i /path/to/container/image.tar.gz -p bueno_branson.py
```

<br/>

# Experiment Configuration:

Experiment configuration is establish and in experiments/config. These
settings include the input file being used by Branson and the installation
directory of Branson itself. The range of values to be tested in the set
of run commands is also modifiable here.
```
# Custom bueno runscript for the Branson mini-app.
# --csv-output 'data.csv'
# --description 'bueno run script for the Branson mini-app.'
# --executable '~/branson/BRANSON'
# --input './experiments/config'
# --name 'branson'
# --runcmds "8, 12, 'mpirun -n %n', 'nidx'"
# --bransonfile './experiments/cube_decomp_test.xml'
{} {}
```

> ### Note: <br/>
> The --input flag refers the bueno run script config file and not to be
> confused with Branson's input file.

<br/>

# Post Analysis:
After execution, the metadata files are stored in the new direcory, sharing
the name of the experiment. The run script's post action created several files
containing information for post analysis, e.g. data.csv.
