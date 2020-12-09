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
import sys

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
            default='./experiments/input'
        )

        cliconfig.argparser.add_argument(
            '--poutfile',
            help="pennant output file",
            default='./experiments/output'
        )


class Experiment:
    '''
    PENNANT benchmark definition
    '''
    def __init__(self, config: experiment.CLIConfiguration):
        '''
        Experiment configuration.
        '''
        experiment.name(config.args.name)
        self.config = config

        # PENNANT input & output files
        self.pinfile = config.args.pinfile
        self.poutfile = config.args.poutfile

        self.data = {
            'command': list(),
            'results': list()
        }

        # Emit program config to terminal.
        self.emit_conf()
        self.add_assets()

    def emit_conf(self):
        '''
        Emit configuration to terminal
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self):
        '''
        Select additional assets to copy
        '''
        metadata.add_asset(metadata.FileAsset(self.config.args.input))
        metadata.add_asset(metadata.FileAsset(self.pinfile))

    def post_action(self, **kwargs):
        '''
        Post experiment iteration action
        '''
        logger.log('# Starting Post Action...')
        cmd = kwargs.pop('command')

        # Record command used in iteration.
        self.data['command'].append(cmd)

        # Record timing data from PENNANT output.
        self.parse_poutfile()
        
    def parse_poutfile(self):
        '''
        Parse timing results information from PENNANT output file.
        '''
        # Open output file.
        lines = []
        with open(self.poutfile, 'rt') as output:
            lines = output.readlines()

        # Search for end of run data.
        pos = -1
        for pos, line in enumerate(lines):
            if line == 'Run complete\n':
                break

        # No data found.
        if pos == -1:
            logger.log('ERROR: EOF reached before end of run data found')
            sys.exit()

        timing = lines[pos + 1 : pos +6]

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
                results.append(item.split(':')[1]) # discard label

        # Append iteration results to Experiment data
        self.data['results'].append(results)

    def run(self, genspec):
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
    
    def report(self):
        logger.emlog(F'# {experiment.name()} Report')
        
        # TODO: Generate report


def main(argv):
    # Program description.
    desc = 'bueno run script for PENNANT experiments.'

    # Default Configuration.
    defaults = experiment.CannedCLIConfiguration.Defaults
    defaults.name = 'pennant'
    defaults.description = desc
    defaults.input = 'experiments/config.txt'
    defaults.executable = '/PENNANT/pennant'
    defaults.runcmds = (0, 2, 'mpicc -n %n', 'nidx + 1')
    defaults.csv_output = 'data.csv'

    # Compile and parse configuration.
    config = experiment.CannedCLIConfiguration(desc, argv, defaults)
    config.parseargs()

    for genspec in experiment.readgs(config.args.input, config):
        # Update config after each iteration
        exp = Experiment(config)
        exp.run(genspec)
        exp.report()

# vim: ft=python ts=4 sts=4 sw=4 expandtab
    