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
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


# SNAP path variables.
GSNAP = '~/SNAP_build/src/gsnap'
S_IN = './experiments/input'
S_OUT = './experiments/output'

# SNAP output file variables.
SO_OFFSET = 5
SO_WIDTH = 15


class Experiment:
    def __init__(self, config):
        '''
        Experiment configuration.
        '''
        self.config = config
        experiment.name(self.config.args.name)
        self.data = {
            'command': list(),
            'starttime': list(),
            'tottime': list()
        }
        self.emit_conf()
        self.add_assets()

    def emit_conf(self):
        '''
        Emit program configuration to terminal.
        '''
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self):
        '''
        Add assets to metadata collection
        '''
        metadata.add_asset(metadata.FileAsset(self.config.args.input))

    def post_action(self, **kwargs) -> None:
        '''
        Custom post action: metadata collection
        '''
        logger.emlog('POST-ACTION')

        cmd = kwargs.pop('command')
        tet = kwargs.pop('exectime')
        stm = kwargs.pop('start_time')

        self.data['command'].append(cmd)
        self.data['starttime'].append(stm)
        self.data['tottime'].append(tet)

        logger.log('retriev SNAP output...')
        self.parse_snapfile()

    def parse_snapfile(self):
        with open(S_OUT) as out_file:
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
        container.run(
            F'mpiexec -n 4 {GSNAP} {S_IN} {S_OUT}',
            preaction=None,
            postaction=self.post_action
        )

def main(argv) -> None:
    # Program description
    desc = 'bueno run script for SNAP experiments.'
    # Default values
    defaults = experiment.CannedCLIConfiguration.Defaults
    defaults.description = experiment.name()

    experiment.name('snap-test')
    
