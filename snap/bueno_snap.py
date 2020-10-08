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

from bueno.public import container
from bueno.public import logger
from bueno.public import metadata


# SNAP output file variables.
SO_OFFSET = 5
SO_WIDTH = 15


class Experiment:
    def __init__(self, config):
        '''
        Experiment configuration.
        '''
        self.name = config['name']
        self.description = config['description']
        self.executable = config['executable']
        self.snap_input = config['input']
        self.snap_output = config['output']

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

            adict = dict()
            adict['Timing Summary'] = {}
            for item in data:  # add items to metadata dict
                label, val = item.split(':')
                adict['Timing Summary'][label] = val

            logger.log('\nAdding metadata file...')
            metadata.add_asset(metadata.YAMLDictAsset(adict, 'timing-metadata'))
            return

    def run(self, genspec):
        snap_exec = genspec['executable']
        infile = genspec['input']
        outfile = genspec['output']

        container.run(
            F'mpiexec -n 4 {snap_exec} {infile} {outfile}',
            preaction=None,
            postaction=self.post_action
        )


def main(argv) -> None:
    # Program description
    desc = 'bueno run script for SNAP experiments.'

    # Default values
    defaults = dict()
    defaults['name'] = 'SNAP'
    defaults['description'] = desc
    defaults['executable'] = '~/SNAP_build/src/gsnap'
    defaults['input'] = './experiments/input'
    defaults['output'] = './experiments/output'

    # Initial configuration
    exp = Experiment(defaults)
    exp.run(defaults)
