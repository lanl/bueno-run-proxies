# bueno-run-proxies | PENNANT

<br/>

## Quick Start:
Execute the bueno run script with default configuration parameters and
assumed build location of pennant's executable with no container.
```Shell
$ bueno run -a none -p bueno_pennant.py
```

<br/>

## Experiment Configuration:
In the experiments directory, the config file outlines the execution parameters
of the bueno run script. Modifications to the execution of this experiment
should take place in this file rather than in the main body of the run script
as the default values defined there are overwritten by the config file. The
options present in config include the name, description, executable, input 
(config) and csv output of the experiment.

Customizing the experiment should be performed at the config file level.
Changes to the run commands (runcmds) impact what level of parallel processing
occurs in pennant as well as how many iterations of testing are performed. The
performance of each is recorded in a new folder sharing the experiment's name,
dated and numbered for review.
```
# Custom bueno run script for PENNANT.
# --csv-output data.csv
# --description 'bueno run script for pennant.'
# --executable '~/PENNANT/build/pennant'
# --input './experiments/config'
# --name 'pennant'
# --runcmds "0, 5, 'mpirun -n %n', 'nidx + 1'"
{} ./experiments/nohsmall/nohsmall.pnt
```

> Note:
> The input defined is the config file for the run script and is not to be
> confused with the pennant input file noshsmall.pnt, likewise, the
> experiment's csv output file is distinct from the output file generated by
> pennant

<br/>

## Script Execution:
```Shell
# Generic, non-containerized application
$ bueno run -a none -p bueno_pennant.py

# With containerized application
$ bueno run -i ~/bueno-proxies-src/pennant/test-pennant.tar.gz -p bueno_pennant.py
```

After sucessful run script execution, the csv report of the timing results
can be found within the new pennant folder alongside other collected metadata
assets. Recording the Cycle, Cstop, Time Tstop and terminal command used for
each iteration of the test.

<br/>

## Los Alamos National Laboratory Code Release
C19133 [bueno](https://github.com/lanl/bueno)

<br/>

-------------------------------------------------------------------------------
Last Modified - 12/24/2020