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


class Configuration(experiment.CLIConfiguration):
    def __init__(self, desc, argv):
        super().__init__(desc, argv)
        # Get the generate specification and process any arguments provided. Do
        # this as early as possible to see an up-to-date version of the config.
        self.genspec = experiment.readgs(self.args.input, self)

    def addargs(self):
        self.argparser.add_argument(
            '--csv-output',
            type=str,
            metavar='CSV_NAME',
            help='Names the generated CSV file produced by a run.',
            required=False,
            default=Configuration.Defaults.csv_output
        )

        self.argparser.add_argument(
            '-d', '--description',
            type=str,
            metavar='DESC',
            help='Describes the experiment.',
            required=False,
            default=Configuration.Defaults.description
        )

        self.argparser.add_argument(
            '--executable',
            type=str,
            metavar='EXEC',
            help="Specifies the executable's path.",
            required=False,
            default=Configuration.Defaults.executable
        )

        self.argparser.add_argument(
            '-i', '--input',
            type=str,
            metavar='INP',
            help='Specifies the path to an experiment input.',
            required=False,
            default=Configuration.Defaults.input
        )

        self.argparser.add_argument(
            '--name',
            type=str,
            help='Names the experiment.',
            required=False,
            default=Configuration.Defaults.experiment_name
        )

        # Add pre-canned options to deal with experiment.runcmds() input.
        experiment.cli_args_add_runcmds_option(
            self,
            opt_required=False,
            opt_default=Configuration.Defaults.rcmds
        )

    class Defaults:
        csv_output = 'data.csv'
        description = experiment.name()
        executable = '/AMG/test/amg'
        input = 'experiments/quick'
        experiment_name = 'AMG'
        rcmds = (0, 2, 'srun -n %n', 'nidx + 1')


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

    def run(self):
        # Generate the run commands for the given experiment.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])
        # The application and its arguments.
        appargs = self.config.genspec.format(self.config.args.executable)

        logger.emlog('# Starting Runs...')
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
        dataw.writerow(header)
        table.addrow(header, withrule=True)
        for solid, numpe, tott, nxyz, pxyz, fom in data:
            row = [solid, numpe, tott, nxyz, pxyz, fom]
            dataw.writerow(row)
            table.addrow(row)

        csvfname = self.config.args.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvfname))
        table.emit()


class Program:
    def __init__(self, argv):
        self.desc = 'bueno run script for AMG experiments.'
        # Experiment configuration, data, and analysis.
        self.experiment = Experiment(Configuration(self.desc, argv))

    def run(self):
        self.experiment.run()
        self.experiment.report()


def main(argv):
    Program(argv).run()

# vim: ft=python ts=4 sts=4 sw=4 expandtab
