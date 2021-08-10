#
# Copyright (c) 2019-2021 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
Bueno run script for the Ember Pattern Library
'''
import typing
import re
import io
import csv

from bueno.public import container
from bueno.public import datasink
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


# pylint: disable=too-few-public-methods
class AddArgsAction(experiment.CLIAddArgsAction):
    '''
    Handle custom argument processing
    '''
    def __call__(self, cliconfig: experiment.CLIConfiguration) -> None:
        '''
        New argument definitions
        '''
        cliconfig.argparser.add_argument(
            '--manual-factors',
            help="Used in place of auto-factorization: [(x, y, z), ..]",
            default=None
        )


def csv_to_list(string: str) -> typing.List[typing.List[int]]:
    '''
    Convert csv style string to grouped list
    '''
    factors = []
    groups = string.split('; ')

    for group in groups:
        temp = []
        for item in group.split(', '):
            temp.append(int(item))
        factors.append(temp)

    return factors


class Experiment:
    '''
    Ember benchmark definition
    '''
    def __init__(self, config: experiment.CLIConfiguration):
        experiment.name(config.args.name)

        # set experiment configuratin, executable
        self.config = config
        self.executable = self.config.args.executable

        self.data: typing.Dict[str, list] = {
            'commands': list(),
            'results': list()
        }

        self.emit_conf()  # Emit config to terminal
        self.add_assets()  # Copy input file to metadata

        # Optional property: manual factors
        self.manual_factors: typing.List[typing.List[int]] = []
        if config.args.manual_factors is not None:
            self.manual_factors = csv_to_list(config.args.manual_factors)

    def emit_conf(self) -> None:
        '''
        Display and record experiment configuration
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self) -> None:
        '''
        Backup metadata assets
        '''
        metadata.add_asset(metadata.FileAsset(self.config.args.input))

    def post_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Post experiment iteration action
        '''
        logger.log('# POST-ACTION')
        logger.log('')
        cmd = kwargs.pop('command')

        # Record command used in iteration.
        self.data['commands'].append(cmd)

        # Record iteration output data
        self.parse_output(list(kwargs.pop('output')))

    def parse_output(self, out1: typing.List[str]) -> None:
        '''
        Parse timing results information from Ember terminal output.
        '''
        for pos, row in enumerate(out1):
            trimmed = re.sub(r'[ ]+', ' ', row)
            if trimmed == '# Time KBytesXchng/Rank-Max MB/S/Rank\n':
                result = out1[pos + 1]
                data = re.sub(r'[ ]+', ',', result).split(',')[1:]
                data[2] = data[2][:-1]
                self.data['results'].append(data)

    def run(self, genspec: str) -> None:
        '''
        Run benchmark test.
        '''
        logger.emlog('# Starting Runs...')

        # Generate run commands for current experiment.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])

        # Create factor registry, or use provided.
        factors = []
        if len(self.manual_factors) == 0:
            for val in range(rcmd[0], rcmd[1] + 1):
                factors.append(experiment.factorize(val, 3))
        else:
            factors = self.manual_factors

        executable = self.config.args.executable
        for i, prun in enumerate(pruns):
            pex = factors[i][0]
            pey = factors[i][1]
            pez = factors[i][2]
            appargs = genspec.format(executable, pex, pey, pez)

            logger.log('')
            container.prun(
                prun,
                appargs,
                postaction=self.post_action
            )

    def report(self) -> None:
        '''
        Generate report
        '''
        logger.emlog(F'# {self.config.args.name} Report')
        logger.log('creating report...\n')

        # Setup Table
        table = datasink.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)

        header = ['Time', 'KBytesXchng/Rank-Max', 'MB/S/Rank', 'Command']
        dataraw.writerow(header)
        table.addrow(header)

        # Populate table.
        for index, entry in enumerate(self.data['results']):
            table.addrow(entry)
            entry.append(self.data['commands'][index])
            dataraw.writerow(entry)

        # Write table to csv & display to terminal.
        csvname = self.config.args.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvname))
        table.emit()
        logger.log('')


def main(argv: typing.List[str]) -> None:
    '''
    Bueno run script for Ember Pattern Library
    '''
    # Program description
    desc = 'bueno run script for Ember experiment'

    # Default values
    defaults = experiment.DefaultCLIConfiguration.Defaults
    defaults.name = 'ember'
    defaults.description = desc
    defaults.executable = '~/ember/mpi/halo3d/halo3d'
    defaults.input = './experiments/config'
    defaults.csv_output = './data.csv'
    defaults.runcmds = (4, 6, 'mpirun -n %n', 'nidx')

    # Initial configuration
    config = experiment.DefaultCLIConfiguration(desc, argv, defaults)
    config.addargs(AddArgsAction)

    # Parse provided arguments.
    config.parseargs()
    for genspec in experiment.readgs(config.args.input, config):
        # Note that config is updated by readgs each iteration.
        exp = Experiment(config)
        exp.run(genspec)
        exp.report()

# vim: ft=python ts=4 sts=4 sw=4 expandtab
