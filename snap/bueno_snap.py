#
# Written by Jacob Dickens, Sept-2020
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
Bueno run script for the SN Application Proxy (SNAP).
'''

import re
import io
import csv
import sys
import typing

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


# SNAP output table variables.
SO_OFFSET = 5
SO_WIDTH = 15


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
        self.add_assets()  # Copy input file to metadata record

    def emit_conf(self) -> None:
        '''
        Display & record Experiment configuration.
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self) -> None:
        '''
        Backup input and output files in metadata (including snap files).
        '''
        metadata.add_asset(metadata.FileAsset(self.config.args.input))
        metadata.add_asset(metadata.FileAsset(self.snap_input))
        metadata.add_asset(metadata.FileAsset(self.snap_output))

    def pre_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Custom pre action: update snap input
        '''
        logger.emlog('# PRE-ACTION')
        logger.log('Updating snap input...')

        # Fetch volume for decomposition from command execution.
        # Perform factor evaluation.
        volume = int(str(kwargs["command"]).split(" ")[2])
        dimensions = experiment.evaluate_factors(volume, 2)
        logger.log('Factor calculated!')

        # Parse snap input file to list
        # Update configuration settings to match volume.
        with open(self.snap_input) as in_file:
            lines = in_file.readlines()

        updated = []
        for row in lines:
            if row[2:6] == 'npey':
                updated.append(F'  npey={dimensions[0]}\n')
            elif row[2:6] == 'npez':
                updated.append(F'  npez={dimensions[1]}\n')
            elif row[2:4] == 'ny':
                updated.append(F'  ny={dimensions[0]}\n')
            elif row[2:4] == 'nz':
                updated.append(F'  nz={dimensions[1]}\n')
            else:
                updated.append(row)

        # overwrite SNAP input file
        with open(self.snap_input, 'wt') as in_file:
            in_file.writelines(updated)

    def post_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Custom post action: metadata collection.
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
            table_pos = -1  # Time table position

            for num, line in enumerate(lines):
                # Search for time table
                if 'keyword Timing Summary' in line:
                    table_pos = num
                    logger.log(F'Found time table on line: {table_pos}\n')

            # No table found.
            if table_pos == -1:
                logger.log('ERROR: EOF reached before time table found')
                sys.exit()

            start = table_pos + SO_OFFSET
            end = table_pos + SO_OFFSET + SO_WIDTH
            time_table = lines[start:end]  # Isolate table lines
            results = []

            # Format data string for yaml file
            for row in time_table:
                row = row.strip()
                row = re.sub(r'[ ]{2,}', ':', row)

                if row == '':  # Skip empty
                    continue

                # Else append formatted item.
                logger.log(F'[data] {row}')
                results.append(row.split(':')[1])

            # Add items to metadata dictionary.
            self.data['results'].append(results)

            # Save dictionary data.
            logger.log('\nAdding metadata file...')
            metadata.add_asset(metadata.YAMLDictAsset(
                self.data,
                'timing-metadata'
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
        appargs = genspec.format(executable)
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
        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)

        # Column header
        header = [
            'Parallel Setup', 'Input', 'Setup', 'Solve', 'Parameter Setup',
            'Outer Source', 'Inner Iteration', 'Inner Source',
            'Transport Sweet', 'Inner Misc Ops', 'Solution Misc Ops',
            'Output', 'Total Execution Time', 'Grind Time', 'Command'
        ]
        dataraw.writerow(header)
        table.addrow(header)

        # Populate csv table.
        for index, entry in enumerate(self.data['results']):
            entry.append(self.data['commands'][index])
            dataraw.writerow(entry)
            table.addrow(entry)

        csvfname = self.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvfname))
        table.emit()
        logger.log('')


def main(argv: typing.List[str]) -> None:
    '''
    Bueno run script for SN Application Proxy (SNAP).
    '''
    # Program description
    desc = 'bueno run script for SNAP experiments.'

    # Default values
    defaults = experiment.CannedCLIConfiguration.Defaults
    defaults.csv_output = './data.csv'
    defaults.description = desc
    defaults.executable = '~/SNAP_build/src/gsnap'
    defaults.input = './experiments/config'
    defaults.name = 'snap'
    defaults.runcmds = (4, 6, 'mpiexec -n %n', 'nidx')

    # Initial configuration
    config = experiment.CannedCLIConfiguration(desc, argv, defaults)
    config.addargs(AddArgsAction)

    # Parse provided arguments.
    config.parseargs()
    for genspec in experiment.readgs(config.args.input, config):
        # Note that config is updated by readgs each iteration.
        exp = Experiment(config)
        exp.run(genspec)
        exp.report()
