# bueno-run-proxies | Ember

<br/>

## Quick Start:
Execute the bueno run script with the default configuration parameters and
assumed build location of Ember's executable with no containerized
application.
```Shell
$ bueno run -a none -p bueno_ember.py
```

<br/>

## Experiment Configuration:
Changes to the benchmark configuration settings can be made in the config
file found in the experiments directory. This includes changes to the flags
used when executing the ember application. However, the values assigned to
pex, pey and pez are dynamically assigned at runtime. This is because the
product of these three values must equal the one assigned to the -n flag.
The range of values, as usual in our run scripts, is defined by the first
two numbers of the runcmds line.
```
# Custom bueno runscript for Ember.
# --csv-output data.csv
# --description 'bueno run script for Ember.'
# --executable '~/ember/mpi/halo3d/halo3d'
# --name 'ember'
# --runcmds "20, 25, 'mpirun -n %n', 'nidx'"
{} -pex {} -pey {} -pez {} -nx 8 -ny 8 -nz 8 -iterations 100 -vars 8 -sleep 100
```
> ### Note: <br/>
> If you would prefer to use different values than are provided by the
> factorization function, you can explicitly define them in the config file.
> For example:
> <br/> # --runcmds "8, 9, 'mpirun -n %n', 'nidx'"
> <br/> # --manual-factors "2, 2, 2; 3, 3, 1" <br/>
> <br/>
> Bear in mind that these manual factors must follow the product rule
> mentioned previously and each group of factors must be separated by a
> semicolon.

<br/>

## Post Experiment:
Upon concluding the experiment iterations, all the recorded data displayed in
the terminal table, can be found in the time-stamped directory within
data.csv. Recorded data includes time data printed to terminal at runtime for
each experiment iteration as well as the command used.

<br/>

## Los Alamos National Laboratory Code Release
C19133 [bueno](https://github.com/lanl/bueno)

<br/>

-------------------------------------------------------------------------------
Last Modified - 02/01/2021