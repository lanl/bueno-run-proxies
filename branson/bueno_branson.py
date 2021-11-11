#
# Copyright (c) 2019-2021 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
bueno run script for Branson A Monte Carlo transport mini-app for studying new
parallel algorithms
'''

import typing
import io
import csv

from bueno.public import container
from bueno.public import datasink
from bueno.public import experiment
from bueno.public import logger
from bueno.public import data
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
            '--bransonfile',
            help="path to Branson input file",
            default='./experiments/cube_decomp_test.xml'
        )


class Experiment:
    '''
    Branson benchmark defition
    '''
    def __init__(self, config: experiment.CLIConfiguration):
        '''
        Experiment configuration
        '''
        experiment.name(config.args.name)

        # Set experiment configuration, executable and data output.
        self.config = config
        self.executable = config.args.executable
        self.csv_output = config.args.csv_output

        self.data: typing.Dict[str, list] = {
            'commands': list(),
            'results': list()
        }

        self.emit_conf()
        self.add_assets()

        # Labels of data to be obtained from app ouput.
        self.keywords = [
            'Total cells requested',
            'Total cells sent',
            'Total cell messages',
            'Total transport',
            'Total setup'
        ]

    def emit_conf(self) -> None:
        '''
        Display & record experiemtn configuration
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self) -> None:
        '''
        Backup input and output files in data
        '''
        data.add_asset(data.FileAsset(self.config.args.input))
        data.add_asset(data.FileAsset(self.config.args.bransonfile))

    def post_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Custom post action: data collection for report
        '''
        logger.emlog('# Post-ACTION')
        logger.log('Retrieving branson output...')
        cmd = kwargs.pop('command')

        # Record command used.
        # Process snap output.
        self.data['commands'].append(cmd)
        self.parse_output(list(kwargs.pop('output')))

    def parse_output(self, out1: typing.List[str]) -> None:
        '''
        Parse timing results from app EOR terminal output.
        '''
        timetable = []

        # Find time table & populate local.
        for pos, line in enumerate(out1):
            if line.startswith('Total cells requested'):
                logger.log(F'Found EOR table on line: {pos}')
                timetable = out1[pos:]
                break

        # Collect results from current iteration.
        iter_results = []
        for row in timetable:
            # Ignore decorative lines.
            if '*' in row:
                continue

            label, value = row.split(': ')
            if label in self.keywords:
                iter_results.append(value[:-1])  # Remove newline

        # Add iteration results to experiment data.
        self.data['results'].append(iter_results)

    def run(self, genspec: str) -> None:
        '''
        Run benchmark test.
        '''
        logger.emlog('# Starting Runs...')
        print(genspec)

        # Generate run commands for current experiment.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])

        executable = self.config.args.executable
        b_input = self.config.args.bransonfile
        appargs = genspec.format(executable, b_input)
        for prun in pruns:
            logger.log('')
            container.prun(
                prun,
                appargs,
                postaction=self.post_action
            )

    def report(self) -> None:
        '''
        Generate csv report
        '''
        logger.emlog(F'# {self.config.args.name} Report')
        logger.log('Creating report...')

        # Setup table.
        table = datasink.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)

        # Column headers.
        columns = []
        for label in self.keywords:
            columns.append(label)

        dataraw.writerow(columns)
        table.addrow(columns)

        # Populate table.
        for index, entry in enumerate(self.data['results']):
            table.addrow(entry)
            entry.append(self.data['commands'][index])
            dataraw.writerow(entry)

        # Write table to csv ad display to terminal.
        csvname = self.config.args.csv_output
        data.add_asset(data.StringIOAsset(sio, csvname))
        table.emit()
        logger.log('')


def main(argv: typing.List[str]) -> None:
    '''
    Bueno run script for Branson Monte Carlo transport mini-app
    '''
    # Program description
    desc = 'bueno run script for the Branson mini-app'

    # Default values
    defaults = experiment.DefaultCLIConfiguration.Defaults
    defaults.csv_output = './data.csv'
    defaults.description = desc
    defaults.executable = '~/branson/BRANSON'
    defaults.input = './experiments/config'
    defaults.name = 'branson'
    defaults.runcmds = (4, 6, 'mpiexec -n %n', 'nidx')

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
