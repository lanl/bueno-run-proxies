#
# Copyright (c) 2019-2021 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
bueno run script for the SN Application Proxy (SNAP).
'''

import re
import io
import csv
import typing

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
            '--snapinfile',
            help="location of snap's input file",
            default='./experiments/input'
        )

        cliconfig.argparser.add_argument(
            '--snapoutfile',
            help="location of snap's output file",
            default='./experiments/output'
        )


class Experiment:
    '''
    SNAP benchmark definition
    '''
    def __init__(self, config: experiment.CLIConfiguration):
        '''
        Experiment configuration.
        '''
        experiment.name(config.args.name)

        # set experiment configuration, executable and data output.
        self.config = config
        self.executable = self.config.args.executable
        self.csv_output = self.config.args.csv_output

        # establish custom snap properties.
        self.snap_input = self.config.args.snapinfile
        self.snap_output = self.config.args.snapoutfile

        self.data: typing.Dict[str, list] = {
            'commands': list(),
            'results': list()
        }

        self.emit_conf()  # Emit config to terminal
        self.add_assets()  # Copy input file to data record

        # Label of data to be obtained.
        self.keywords = [
            'Parallel Setup',
            'Input',
            'Setup',
            'Solve',
            'Parameter Setup',
            'Outer Source',
            'Inner Iterations',
            'Inner Source',
            'Transport Sweeps',
            'Inner Misc Ops',
            'Solution Misc Ops',
            'Output',
            'Total Execution time',
            'Grind Time (nanoseconds)',
        ]

    def emit_conf(self) -> None:
        '''
        Display & record Experiment configuration.
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self) -> None:
        '''
        Backup input and output files in data (including snap files).
        '''
        data.add_asset(data.FileAsset(self.config.args.input))
        data.add_asset(data.FileAsset(self.snap_input))
        data.add_asset(data.FileAsset(self.snap_output))

    def pre_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Custom pre action: update snap input
        '''
        logger.emlog('# PRE-ACTION')
        logger.log('Updating snap input...')

        # Fetch volume for decomposition from command execution.
        # Perform factor evaluation.
        volume = int(str(kwargs["command"]).split(" ")[2])
        dimensions = experiment.factorize(volume, 2)
        logger.log('Factor calculated!')

        # Parse snap input file to list
        # Update configuration settings to match volume.
        with open(self.snap_input) as in_file:
            lines = in_file.readlines()

        updated = []
        for row in lines:
            trim = row.strip()
            if trim.startswith('npey'):
                updated.append(F'      npey={dimensions[0]}\n')
            elif trim.startswith('npez'):
                updated.append(F'      npez={dimensions[1]}\n')
            elif trim.startswith('ny'):
                updated.append(F'      ny={dimensions[0]}\n')
            elif trim.startswith('nz'):
                updated.append(F'      nz={dimensions[1]}\n')
            else:
                updated.append(row)

        # overwrite SNAP input file
        with open(self.snap_input, 'wt') as in_file:
            in_file.writelines(updated)
        logger.log('')

    def post_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Custom post action: data collection.
        '''
        logger.emlog('# POST-ACTION')
        logger.log('Retrieving SNAP output...')

        # Record command used.
        # Process snap output.
        self.data['commands'].append(str(kwargs['command']))
        self.parse_snapfile()

    def parse_snapfile(self) -> None:
        '''
        Collect time data from snap output file.
        '''
        with open(self.snap_output) as out_file:
            lines = out_file.readlines()
            time_table = []

            # Search for time table.
            for pos, line in enumerate(lines):
                if line.lstrip().startswith('keyword Timing Summary'):
                    logger.log(F'Found time table on line: {pos}\n')
                    time_table = lines[pos + 1:]
                    break

            # Collect iteration results.
            results = []
            for row in time_table:
                # trim white space, su
                trimmed = re.sub(r'[ ]{2,}', ':', row.strip())

                # Skip empty or decorative
                if trimmed == '' or '*' in trimmed:
                    continue

                label, value = trimmed.split(':')

                if label in self.keywords:
                    results.append(value)

            # Add iteration results to experiment data.
            self.data['results'].append(results)

            # Save dictionary data.
            logger.log('\nAdding data file...')
            data.add_asset(data.YAMLDictAsset(
                self.data,
                'timing-data'
            ))
            return

    def run(self, genspec: str) -> None:
        '''
        Run benchmark test.
        '''
        logger.emlog('# Starting Runs...')

        # Generate run commands for current experiment.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])

        executable = self.config.args.executable
        s_input = self.snap_input
        s_output = self.snap_output
        appargs = genspec.format(executable, s_input, s_output)
        for prun in pruns:
            logger.log('')
            container.prun(
                prun,
                appargs,
                preaction=self.pre_action,
                postaction=self.post_action
            )

    def report(self) -> None:
        '''
        Generate csv report.
        '''
        logger.emlog(F'# {self.config.args.name} Report')
        logger.log('creating report...\n')

        # Setup table
        table = datasink.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)

        # Column header
        header = self.keywords
        dataraw.writerow(header)
        table.addrow(header)

        # Populate csv table.
        for index, entry in enumerate(self.data['results']):
            table.addrow(entry)  # Terminal table.

            # Add command column to csv file.
            entry.append(self.data['commands'][index])
            dataraw.writerow(entry)

        csvfname = self.csv_output
        data.add_asset(data.StringIOAsset(sio, csvfname))
        table.emit()
        logger.log('')


def main(argv: typing.List[str]) -> None:
    '''
    Bueno run script for SN Application Proxy (SNAP).
    '''
    # Program description
    desc = 'bueno run script for SNAP experiments.'

    # Default values
    defaults = experiment.DefaultCLIConfiguration.Defaults
    defaults.csv_output = './data.csv'
    defaults.description = desc
    defaults.executable = '~/SNAP_build/src/gsnap'
    defaults.input = './experiments/config'
    defaults.name = 'snap'
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
