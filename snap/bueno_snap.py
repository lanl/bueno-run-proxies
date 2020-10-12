#
# Written by Jacob Dickens, 2020
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

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


# SNAP output file variables.
SO_OFFSET = 5
SO_WIDTH = 15


class Experiment:
    def __init__(self, config):
        '''
        Experiment configuration.
        '''
        self.config = config  # experiment configuration
        experiment.name(self.config.args.name)  # set experiment name

        self.csv_output = self.config.args.csv_output
        self.snap_output = './output'  # TODO: addargs implimentation

        exe = self.config.args.executable
        s_in = self.config.args.input
        s_out = self.snap_output
        self.cmd = F'mpiexec -n 4 {exe} {s_in} {s_out}'

        self.data = {
            'Timing Summary': dict()
        }

        self.emit_conf()  # emit config to terminal
        self.add_assets()  # copy input file to metadata record

    def emit_conf(self):
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self):
        metadata.add_asset(metadata.FileAsset(self.config.args.input))
        metadata.add_asset(metadata.FileAsset(self.snap_output))

    def post_action(self, **kwargs) -> None:
        '''
        Custom post action: metadata collection
        '''
        logger.emlog('# POST-ACTION')
        logger.log('Retrieving SNAP output...')
        self.parse_snapfile()

    def parse_snapfile(self):
        with open(self.snap_output) as out_file:
            lines = out_file.readlines()
            table_pos = -1  # time table position

            for num, line in enumerate(lines):
                if 'keyword Timing Summary' in line:
                    table_pos = num
                    logger.log(F'Found time table on line: {table_pos}\n')

            if table_pos == -1:
                logger.log('ERROR: EOF reached before time table found')
                return

            start = table_pos + SO_OFFSET
            end = table_pos + SO_OFFSET + SO_WIDTH
            time_table = lines[start:end]  # isolate table lines
            data = []

            for row in time_table:  # format data string
                row = row.strip()
                row = re.sub(r'[ ]{2,}', ': ', row)

                if row == '':  # skip empty
                    continue

                logger.log(F'[data] {row}')
                data.append(row)  # append formatted item

            for item in data:  # add items to metadata dict
                label, val = item.split(':')
                self.data['Timing Summary'][label] = val  # populate metadata file

            logger.log('\nAdding metadata file...')
            metadata.add_asset(metadata.YAMLDictAsset(
                self.data['Timing Summary'],
                'timing-metadata'
            ))
            return

    def run(self, genspec):
        container.run(
            self.cmd,
            preaction=None,
            postaction=self.post_action
        )

    def report(self):
        logger.emlog(F'# {self.config.args.name} Report')
        logger.log('creating report...')

        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataraw = csv.writer(sio)
        dataraw.writerow([F'## {self.config.args.description}'])

        # Generic data.
        header = ['# EXECUTED:']
        dataraw.writerow(header)
        dataraw.writerow([self.cmd])
        dataraw.writerow([])

        logger.log(header)
        logger.log(self.cmd)
        logger.log('')

        # Time Summary Data.
        header = ['# TIMING SUMMARY:']
        dataraw.writerow(header)
        table.addrow(header)
        for label in self.data['Timing Summary']:
            value = self.data['Timing Summary'][label]
            dataraw.writerow([label, value])
            table.addrow([label, value])

        csvfname = self.csv_output
        metadata.add_asset(metadata.StringIOAsset(sio, csvfname))
        table.emit()


def main(argv) -> None:
    #experiment.name('snap-test')

    # Program description
    desc = 'bueno run script for SNAP experiments.'

    # Default values
    defaults = experiment.CannedCLIConfiguration.Defaults
    defaults.csv_output = './data.csv'
    defaults.description = desc
    defaults.executable = '~/SNAP_build/src/gsnap'
    defaults.input = './experiments/input'
    defaults.name = 'snap'
    
    #defaults['output'] = './output'

    # Initial configuration
    config = experiment.CannedCLIConfiguration(desc, argv, defaults)
    #config.addargs(output)

    # parse provided arguments.
    config.parseargs()
    for genspec in experiment.readgs(config.args.input, config):
        # Note that config is updated by readgs each iteration
        exp = Experiment(config)
        exp.run(genspec)
        exp.report()
