#
# Copyright (c) 2019-2020 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
bueno run script for AMG, a parallel algebraic multigrid solver.
'''

import csv
import io
import re

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


class Experiment:
    def __init__(self, config):
        # The experiment configuration.
        self.config = config
        # Set the experiment's name
        experiment.name(self.config.args.name)
        # Data container.
        self.data = {
            'commands': list(),
            'numpe': list(),
            'tottime': list(),
            'solver_id': list(),
            'nxnynz': list(),
            'pxpypz': list(),
            'fom': list()
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

        self.data['commands'].append(cmd)
        self.data['tottime'].append(tet)

        numpe_match = re.search(r'\s+-n\s?(?P<numpe>[0-9]+)', cmd)
        if numpe_match is None:
            estr = F"Cannot determine numpe from:'{cmd}'"
            raise ValueError(estr)
        numpe = int(numpe_match.group('numpe'))
        self.data['numpe'].append(numpe)

        self._parsenstore(kwargs.pop('output'))

    def _parsenstore(self, outl):
        def parsel(line):
            return line.split(':')[1]

        lines = [x.rstrip() for x in outl]
        for line in lines:
            res = re.search(r'\s*solver ID\s*=\s*(?P<solid>[0-9]+)', line)
            if res is not None:
                self.data['solver_id'].append(res.group('solid'))
                continue

            res = re.search(r'\s*\(Nx, Ny, Nz\)\s*=\s*\((?P<nx>[0-9]+), '
                            r'(?P<ny>[0-9]+), (?P<nz>[0-9]+)\)', line)
            if res is not None:
                nxnynz = F"{res.group('nx')}," \
                         F"{res.group('ny')}," \
                         F"{res.group('nz')}"
                self.data['nxnynz'].append(nxnynz)
                continue

            res = re.search(r'\s*\(Px, Py, Pz\)\s*=\s*\((?P<px>[0-9]+), '
                            r'(?P<py>[0-9]+), (?P<pz>[0-9]+)\)', line)
            if res is not None:
                pxpypz = F"{res.group('px')}," \
                         F"{res.group('py')}," \
                         F"{res.group('pz')}"
                self.data['pxpypz'].append(pxpypz)
                continue

            if line.startswith('Figure of Merit'):
                self.data['fom'].append(parsel(line))
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
            'solver_id',
            'numpe',
            'tottime',
            'nx,ny,nz',
            'px,py,pz',
            'fom'
        ]

        data = zip(
            self.data['solver_id'],
            self.data['numpe'],
            self.data['tottime'],
            self.data['nxnynz'],
            self.data['pxpypz'],
            self.data['fom']
        )

        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataw = csv.writer(sio)
        dataw.writerow([F'## {self.config.args.description}'])
        dataw.writerow(header)
        table.addrow(header, withrule=True)
        for solid, numpe, tott, nxyz, pxyz, fom in data:
            row = [solid, numpe, tott, nxyz, pxyz, fom]
            dataw.writerow(row)
            table.addrow(row)

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
    defaults.executable = '/AMG/test/amg'
    defaults.input = 'experiments/quick'
    defaults.name = 'AMG'
    defaults.runcmds = (0, 2, 'srun -n %n', 'nidx + 1')
    # Initial configuration
    config = experiment.CannedCLIConfiguration(desc, argv, defaults)
    # Parse provided arguments
    config.parseargs()
    for genspec in experiment.readgs(config.args.input, config):
        # Note that config is updated by readgs after each iteration.
        exprmnt = Experiment(config)
        exprmnt.run(genspec)
        exprmnt.report()

# vim: ft=python ts=4 sts=4 sw=4 expandtab
