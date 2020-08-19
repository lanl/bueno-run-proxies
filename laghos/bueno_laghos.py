#
# Copyright (c) 2019-2020 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
bueno run script for the Laghos miniapp.
'''

import csv
import io
import os
import re

from bueno.public import container
from bueno.public import experiment
from bueno.public import host
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils

# Import extras
try:
    import icaptdb
except ImportError:
    pass
else:
    metadata.add_asset(metadata.PythonModuleAsset(icaptdb))


class FOMFactory:
    @staticmethod
    def build(name, value):
        if name == 'cgh1':
            desc = 'CG (H1) total time'
            units = 's'
            return experiment.FOM(name, desc, units, value)
        if name == 'cgl2':
            desc = 'CG (L2) total time'
            units = 's'
            return experiment.FOM(name, desc, units, value)
        return None


class Experiment:
    def __init__(self, config):
        # The experiment configuration.
        self.config = config
        # Set the experiment's name
        experiment.name(self.config.args.name)
        # Data container.
        self.data = {
            'command': list(),
            'numpe': list(),
            'nthread': list(),
            'starttime': list(),
            'tottime': list(),
            'cgh1': list(),
            'cgl2': list()
        }
        # Emit program configuration to terminal.
        self.emit_conf()
        # Add assets to collection of metadata.
        self.add_assets()

    def emit_conf(self):
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self):
        metadata.add_asset(metadata.FileAsset(self.config.args.input))

    def post_action(self, **kwargs):
        cmd = kwargs.pop('command')
        tet = kwargs.pop('exectime')
        stm = kwargs.pop('start_time')

        self.data['command'].append(cmd)
        self.data['starttime'].append(stm)
        self.data['tottime'].append(tet)

        numpe_match = re.search(r'\s+-n\s?(?P<numpe>[0-9]+)', cmd)
        if numpe_match is None:
            estr = F"Cannot determine numpe from:'{cmd}'"
            raise ValueError(estr)
        numpe = int(numpe_match.group('numpe'))
        self.data['numpe'].append(numpe)
        # We currently support only single-threaded runs.
        self.data['nthread'].append(1)

        self._parsenstore(kwargs.pop('output'))

    def _parsenstore(self, outl):
        def parsel(line):
            return float(line.split(':')[1])

        lines = [x.rstrip() for x in outl]
        for line in lines:
            if line.startswith('CG (H1) total time:'):
                self.data['cgh1'].append(parsel(line))
                continue
            if line.startswith('CG (L2) total time:'):
                self.data['cgl2'].append(parsel(line))
                continue

    def run(self, genspec):
        logger.emlog('# Starting Runs...')
        # Generate the run commands for the given experiment.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])
        # The application and its arguments.
        executable = self.config.args.executable
        appargs = genspec.format(executable)
        for prun in pruns:
            logger.log('')
            container.prun(prun, appargs, postaction=self.post_action)

    def report(self):
        logger.emlog(F'# {experiment.name()} Report')

        header = [
            'numpe',
            'tottime',
            'cgh1',
            'cgl2'
        ]

        data = zip(
            self.data['command'],
            self.data['starttime'],
            self.data['numpe'],
            self.data['nthread'],
            self.data['tottime'],
            self.data['cgh1'],
            self.data['cgl2']
        )

        icapt_rds = None
        if utils.module_imported('icaptdb'):
            icapt_rds = icaptdb.RunDataStore(self.config.args)

        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataw = csv.writer(sio)
        dataw.writerow([F'## {self.config.args.description}'])
        dataw.writerow(header)
        table.addrow(header, withrule=True)
        for cmd, stime, numpe, nthread, tott, cgh1, cgl2 in data:
            row = [numpe, tott, cgh1, cgl2]
            dataw.writerow(row)
            table.addrow(row)
            if icapt_rds is not None:
                icapt_rds.add(
                    stime.strftime('%a %b %d %H:%M:%S %Y'),
                    tott,
                    numpe,
                    nthread,
                    cmd,
                    (FOMFactory.build('cgh1', cgh1),
                     FOMFactory.build('cgl2', cgl2))
                )

        csvfname = self.config.args.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvfname))
        table.emit()
        logger.log('')


def main(argv):
    # Program description
    desc = 'bueno run script for Laghos experiments.'
    # Default values
    defaults = experiment.CannedCLIConfiguration.Defaults
    defaults.csv_output = 'data.csv'
    defaults.description = experiment.name()
    defaults.executable = '/laghos/Laghos/laghos'
    defaults.input = 'experiments/quick-sedov-blast2D'
    defaults.name = 'laghos'
    defaults.runcmds = (0, 2, 'srun -n %n', 'nidx + 1')
    # Initial configuration
    config = experiment.CannedCLIConfiguration(desc, argv, defaults)
    # Update configuration to include extra arguments
    if utils.module_imported('icaptdb'):
        config.addargs(icaptdb.AddArgsAction)
    # Parse provided arguments
    config.parseargs()
    for genspec in experiment.readgs(config.args.input, config):
        # Note that config is updated by readgs after each iteration.
        exprmnt = Experiment(config)
        exprmnt.run(genspec)
        exprmnt.report()

# vim: ft=python ts=4 sts=4 sw=4 expandtab
