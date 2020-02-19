#
# Copyright (c) 2019-2020 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils

import csv
import re


class Configuration(experiment.CLIConfiguration):

    def __init__(self, desc, argv):
        super().__init__(desc, argv)
        # Get the generate specification and process any arguments provided. Do
        # this as early as possible to see an up-to-date version of the config.
        # TODO(skg) Provide a way to specify the run parameters as an argument.
        # Something like: --prun-args '-n {{}} -N {{}}'
        self.genspec = experiment.readgs(self.args.input, self)

    def addargs(self):
        self.argparser.add_argument(
            '--csv-output',
            type=str,
            help='Names the generated CSV file produced by a run.',
            required=False,
            default=Configuration.Defaults.csv_output
        )

        self.argparser.add_argument(
            '-d', '--description',
            type=str,
            help='Describes the experiment.',
            required=False,
            default=Configuration.Defaults.description
        )

        self.argparser.add_argument(
            '--executable',
            type=str,
            help="Specifies the executable's path.",
            required=False,
            default=Configuration.Defaults.executable
        )

        # TODO(skg) Document how relative paths work in bueno run scripts. Note
        # that paths are relative to the run script.
        self.argparser.add_argument(
            '-i', '--input',
            type=str,
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

        self.argparser.add_argument(
            '--ppn',
            type=int,
            help='Specifies the number of processors per node.',
            required=False,
            default=Configuration.Defaults.ppn
        )

        self.argparser.add_argument(
            '--prun',
            type=str,
            help='Specifies the parallel launcher to use.',
            required=False,
            default=Configuration.Defaults.prun
        )

    class Defaults:
        csv_output = 'data.csv'
        description = experiment.name()
        executable = '/laghos/Laghos/laghos'
        input = 'experiments/quick-sedov-blast2D'
        experiment_name = 'laghos'
        # TODO(skg)
        ppn = None
        prun = 'mpiexec'


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

        self.data['commands'].append(cmd)
        self.data['tottime'].append(tet)

        numpe_match = re.search(
            # TODO(skg) Get -n from cmd matrix.
            self.config.args.prun + r' -n (?P<numpe>[0-9]+)',
            cmd
        )
        if numpe_match is None:
            es = F"Cannot determine numpe from:'{cmd}'"
            raise ValueError(es)
        numpe = int(numpe_match.group('numpe'))
        self.data['numpe'].append(numpe)

        self._parsenstore(kwargs.pop('output'))

    def _parsenstore(self, outl):
        def parsel(l):
            return float(l.split(':')[1])

        lines = [x.rstrip() for x in outl]
        for line in lines:
            if line.startswith('CG (H1) total time:'):
                self.data['cgh1'].append(parsel(line))
                continue
            if line.startswith('CG (L2) total time:'):
                self.data['cgl2'].append(parsel(line))
                continue

    def run(self):
        # TODO(skg): Add support for multiple specs in an input file.
        # Generate the run commands for the given experiment.
        runcmds = experiment.generate(
            self.config.genspec.format(
                self.config.args.prun,
                self.config.args.executable
            ),
            # TODO(skg) Add argument that allows generation of this.
            [2, 4]
        )

        logger.emlog('# Starting Runs...')

        for r in runcmds:
            logger.log('')
            container.run(r, postaction=self.post_action)

    def report(self):
        logger.emlog(F'# {experiment.name()} Report')

        header = [
            'numpe',
            'tottime',
            'cgh1',
            'cgl2'
        ]

        data = zip(
            self.data['numpe'],
            self.data['tottime'],
            self.data['cgh1'],
            self.data['cgl2']
        )

        table = utils.Table()
        csvfname = self.config.args.csv_output
        with open(csvfname, 'w', newline='') as csvfile:
            dataw = csv.writer(csvfile)
            dataw.writerow(header)
            table.addrow(header, withrule=True)
            for numpe, t, cgh1, cgl2 in data:
                row = [numpe, t, cgh1, cgl2]
                dataw.writerow(row)
                table.addrow(row)

        metadata.add_asset(metadata.FileAsset(csvfname))
        table.emit()


class Laghos:
    def __init__(self, argv):
        self.desc = 'bueno run script for Laghos experiments.'
        # Experiment configuration, data, and analysis.
        self.experiment = Experiment(Configuration(self.desc, argv))

    def run(self):
        self.experiment.run()
        self.experiment.report()


def main(argv):
    Laghos(argv).run()
