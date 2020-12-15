#
# Written by Jacob Dickens, Dec-2020
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
Bueno run script for the unstructured mesh physics mini-app,
PENNANT
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
            '--pinfile',
            help="pennant input file",
            default='./experiments/nohsmall/nohsmall.pnt'
        )

class Experiment:
    '''
    PENNANT benchmark definition
    '''
    def __init__(self, config: experiment.CLIConfiguration) -> None:
        '''
        Experiment configuration.
        '''
        experiment.name(config.args.name)
        self.config = config

        # PENNANT input file
        self.pinfile = config.args.pinfile

        self.data: typing.Dict[str, list] = {
            'commands': list(),
            'results': list()
        }

        # Emit program config to terminal.
        self.emit_conf()
        self.add_assets()

    def emit_conf(self) -> None:
        '''
        Emit configuration to terminal
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self) -> None:
        '''
        Select additional assets to copy
        '''
        metadata.add_asset(metadata.FileAsset(self.config.args.input))
        metadata.add_asset(metadata.FileAsset(self.pinfile))

    def post_action(self, **kwargs: typing.Dict[str, str]) -> None:
        '''
        Post experiment iteration action
        '''
        logger.log('# Starting Post Action...')
        cmd = kwargs.pop('command')

        # Record command used in iteration.
        self.data['commands'].append(cmd)

        # Record timing data from PENNANT terminal output.
        self.parse_output(kwargs.pop('output'))

    def parse_output(self, out1) -> None:
        '''
        Parse timing results information from PENNANT output file.
        '''
        # Search for end of run data.
        pos = -1
        for pos, line in enumerate(out1):
            if line == 'Run complete\n':
                print('Found runtime table!')
                break

        # No data found.
        if pos == -1:
            logger.log('ERROR: No run data found')
            sys.exit()

        timing = out1[pos + 1: pos + 6]

        # Isolate & format end of run data.
        results = []
        for row in timing:
            items = row.split(',')
            for item in items:
                if '*' in item or item == '\n':
                    continue  # Skip empty or decorative lines.

                # Trim whitespace.
                item = re.sub(r'[ ]*\=[ ]+', ':', item)
                item = item.strip()

                # Remove unecessary characters.
                item = re.sub(r'[()]', '', item)
                results.append(item.split(':')[1])  # discard label

        # Append iteration results to Experiment data
        self.data['results'].append(results)

    def run(self, genspec: str) -> None:
        '''
        Experiment iterations definition
        '''
        logger.log('# Starting Runs...')

        # Generate the iterative run commands.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])
        executable = self.config.args.executable
        appargs = genspec.format(executable)

        # Execute generated run commands.
        for prun in pruns:
            logger.log('')
            container.prun(prun, appargs, postaction=self.post_action)

    def report(self) -> None:
        '''
        Generate csv report from test iterations.
        '''
        logger.emlog(F'# {experiment.name()} Report')

        # Setup table.
        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)

        header = ['Cycle', 'Cstop', 'Time', 'Tstop', 'Hydro Cycle', 'Command']
        dataraw.writerow(header)
        table.addrow(header)

        # Populate table.
        for index, entry in enumerate(self.data['results']):
            entry.append(self.data['commands'][index])
            dataraw.writerow(entry)
            table.addrow(entry)

        # Write table to csv & display to terminal.
        csvname = self.config.args.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvname))
        table.emit()
        logger.log('')


def main(argv: typing.List[str]) -> None:
    '''
    Setup and start experiment.
    '''
    # Program description.
    desc = 'bueno run script for PENNANT experiments.'

    # Default Configuration.
    defaults = experiment.CannedCLIConfiguration.Defaults
    defaults.name = 'pennant'
    defaults.description = desc
    defaults.input = './experiments/config.txt'
    defaults.executable = '~/PENNANT/build/pennant'
    defaults.runcmds = (2, 2, 'mpirun -n %n', 'nidx + 1')
    defaults.csv_output = 'data.csv'

    # Compile and parse configuration.
    config = experiment.CannedCLIConfiguration(desc, argv, defaults)
    config.addargs(AddArgsAction)
    config.parseargs()

    for genspec in experiment.readgs(config.args.input, config):
        # Update config after each iteration
        exp = Experiment(config)
        exp.run(genspec)
        exp.report()

# vim: ft=python ts=4 sts=4 sw=4 expandtab
