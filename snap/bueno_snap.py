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
import os
import csv
import argparse

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


# SNAP output table variables.
SO_OFFSET = 5
SO_WIDTH = 15


class AddArgsAction(experiment.CLIAddArgsAction):
    '''
    Handle custom argument processing
    '''
    class SnapOutfileAction(argparse.Action):
        '''
        Qrgument structure for SNAP input & output files
        '''
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super().__init__(option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            # Validate provided file path
            # Display custom error if not
            if not os.path.isfile(values):
                estr = F'{values} is not a valid file! Cannot continue!'
                parser.error(estr)
            setattr(namespace, self.dest, values)

    def __call__(self, cliconfig):
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
    def __init__(self, config):
        '''
        Experiment configuration.
        '''
        self.config = config  # The experiment configuration.
        experiment.name(self.config.args.name)  # Set experiment's name

        self.executable = self.config.args.executable
        self.snap_input = self.config.args.snapinfile
        self.snap_output = self.config.args.snapoutfile
        self.csv_output = self.config.args.csv_output

        self.cmd = ''  # Assigned during post action.

        self.data = {
            'Timing Summary': dict()
        }

        self.emit_conf()  # Emit config to terminal
        self.add_assets()  # Copy input file to metadata record

    def emit_conf(self):
        '''
        Display config in terminal
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self):
        '''
        Backup input and output files in metadata
        '''
        metadata.add_asset(metadata.FileAsset(self.config.args.input))
        metadata.add_asset(metadata.FileAsset(self.snap_input))
        metadata.add_asset(metadata.FileAsset(self.snap_output))

    def pre_action(self, **kwargs) -> None:
        '''
        Custom pre action: update snap input
        '''
        logger.emlog('# PRE-ACTION')
        logger.log('Updating snap input')

        # Perform dimension factorisation given volume
        volume = int(kwargs["command"].split(" ")[2])
        dimensions = experiment.evaluate_factors(volume, 2)

        # Read snap input file to list
        with open(self.snap_input) as in_file:
            lines = in_file.readlines()

        # Modify snap configuration list
        updated = []
        for row in lines:
            if 'npey' in row:
                updated.append(F'  npey={dimensions[0]}\n')
            elif 'npez' in row:
                updated.append(F'  npez={dimensions[1]}\n')
            else:
                updated.append(row)

        # overwrite to file
        with open(self.snap_input, 'wt') as in_file:
            in_file.writelines(updated)

    def post_action(self, **kwargs) -> None:
        '''
        Custom post action: metadata collection.
        '''
        logger.emlog('# POST-ACTION')
        logger.log('Retrieving SNAP output...')
        self.cmd = kwargs['command']  # Record command used for report
        self.parse_snapfile()  # Process snap output

    def parse_snapfile(self):
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

            if table_pos == -1:  # No table found
                logger.log('ERROR: EOF reached before time table found')
                return

            start = table_pos + SO_OFFSET
            end = table_pos + SO_OFFSET + SO_WIDTH
            time_table = lines[start:end]  # Isolate table lines
            data = []

            for row in time_table:  # Format data string
                row = row.strip()
                row = re.sub(r'[ ]{2,}', ': ', row)

                if row == '':  # Skip empty
                    continue

                logger.log(F'[data] {row}')
                data.append(row)  # Append formatted item.

            for item in data:  # Add items to metadata dict.
                label, val = item.split(':')
                self.data['Timing Summary'][label] = val

            logger.log('\nAdding metadata file...')
            metadata.add_asset(metadata.YAMLDictAsset(
                self.data['Timing Summary'],
                'timing-metadata'
            ))
            return

    def run(self, genspec):
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

    def report(self):
        '''
        Generate csv report.
        '''
        logger.emlog(F'# {self.config.args.name} Report')
        logger.log('creating report...\n')

        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)
        dataraw.writerow([F'## {self.config.args.description}'])

        # Generic data
        dataraw.writerow(['## Cmd Executed:'])  # write to csv
        dataraw.writerow([self.cmd])

        # Time Summary Data
        header = '## Timing Summary:'
        dataraw.writerow([header])
        table.addrow([header, ''])

        header = ['Code Section', 'Time (s)']
        dataraw.writerow(header)
        table.addrow(header)

        for label in self.data['Timing Summary']:
            value = self.data['Timing Summary'][label]
            dataraw.writerow([label, value])
            table.addrow([label, value])

        csvfname = self.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvfname))
        table.emit()
        logger.log('')


def main(argv) -> None:
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
    defaults.runcmds = (4, 4, 'mpiexec -n %n', 'nidx')

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
