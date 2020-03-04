#
# Copyright (c) 2019-2020 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

from abc import abstractmethod

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils

import csv
import os
import re


def build_parser(bname):
    if bname == 'IMB-MPI1':
        return MPI1Parser()
    raise RuntimeError(F'Unrecognized benchmark name: {bname}')


class BenchmarkOutputParser:
    def __init__(self, lines):
        self.lines = lines
        self.nlines = len(lines)
        self.lineno = 0

    def _line(self, advl):
        if self.lineno == self.nlines:
            return None
        line = self.lines[self.lineno]
        if advl:
            self.advl()
        return line

    def advl(self):
        self.lineno += 1

    def line(self):
        return self._line(False)

    def nextl(self):
        return self._line(True)

    @abstractmethod
    def parse(self):
        pass

class BenchmarkDatum:
    def __init__(self):
        pass



class MPI1Parser(BenchmarkOutputParser):
    def __init__(self, lines):
        super().__init__(lines)

    def _bmname_parse(self):
        line = self.nextl()
        match = re.search('# Benchmarking' + r' (?P<bmname>[A-Za-z_]+)', line)
        if match is None:
            return None
        return match.group('bmname')

    def _numpe_parse(self):
        line = self.nextl()
        match = re.search('# #processes = ' + r'(?P<numpe>[0-9]+)', line)
        # Assume this subparser is called only in the correct context.
        if match is None:
            raise RuntimeError(F"Expected '# #processes', got:\n{line}")
        # Eat the next line.
        self.advl()
        return int(match.group('numpe'))

    def _metrics_parse(self):
        line = self.nextl()
        if line is None:
            raise RuntimeError('Expected metrics line, but got None.')
        return line.strip().split()

    def _stats_parse(self):
        res = list()
        while not utils.emptystr(self.line()):
            line = self.nextl()
            res.append(line.strip().split())
        if len(res) == 0:
            raise RuntimeError('Expected run statistics, but found zero.')
        return res

    def parse(self):
        while self.line() is not None:
            bmname = self._bmname_parse()
            if bmname is None:
                continue
            numpe = self._numpe_parse()
            metrics = self._metrics_parse()
            stats = self._stats_parse()

            print(F'{bmname}, {numpe}')
            print(metrics)
            for s in stats:
                print(s)
            print()


class Configuration(experiment.CLIConfiguration):
    def __init__(self, desc, argv):
        super().__init__(desc, argv)
        # Get the generate specification and process any arguments provided. Do
        # this as early as possible to see an up-to-date version of the config.
        # self.genspec = experiment.readgs(self.args.input, self)

    def addargs(self):
        self.argparser.add_argument(
            '--benchmarks',
            type=str,
            help='Comma-delimited list of IMB benchmarks to run.',
            required=False,
            default=Configuration.Defaults.benchmarks
        )

        self.argparser.add_argument(
            '--bin-dir',
            type=str,
            help='Specifies the base directory of the IMB binaries.',
            required=False,
            default=Configuration.Defaults.bin_dir
        )

        self.argparser.add_argument(
            '--csv-output',
            type=str,
            help='Names the generated CSV file produced by a run.',
            required=False,
            default=Configuration.Defaults.csv_output
        )

        self.argparser.add_argument(
            '-d', '--description',
            type=str,
            help='Describes the experiment.',
            required=False,
            default=Configuration.Defaults.description
        )

        self.argparser.add_argument(
            '--name',
            type=str,
            help='Names the experiment.',
            required=False,
            default=Configuration.Defaults.experiment_name
        )

        self.argparser.add_argument(
            '--ppn',
            type=int,
            help='Specifies the number of processors per node.',
            required=False,
            default=Configuration.Defaults.ppn
        )

        self.argparser.add_argument(
            '--prun',
            type=str,
            help='Specifies the parallel launcher to use.',
            required=False,
            default=Configuration.Defaults.prun
        )

    class Defaults:
        # benchmarks = 'IMB-MPI1, IMB-P2P'
        benchmarks = 'IMB-MPI1'
        bin_dir = '/IMB'
        csv_output = 'imb.csv'
        description = 'Intel MPI Benchmarks'
        experiment_name = 'imb'
        # TODO(skg)
        ppn = None
        prun = 'srun'


class Experiment:
    def __init__(self, config):
        # The experiment configuration.
        self.config = config
        # Set the experiment's name
        experiment.name(self.config.args.name)
        # Data container.
        self.data = {
            'commands': list(),
            'numpe': list(),
            'tottime': list(),
            'cgh1': list(),
            'cgl2': list()
        }
        # Emit program configuration to terminal.
        self.emit_conf()
        # Add assets to collection of metadata.
        self.add_assets()

    def emit_conf(self):
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def add_assets(self):
        return


    def post_action(self, **kwargs):
        cmd = kwargs.pop('command')
        tet = kwargs.pop('exectime')

        self.data['commands'].append(cmd)
        self.data['tottime'].append(tet)

        numpe_match = re.search(
            # TODO(skg) Get -n from cmd matrix.
            self.config.args.prun + r' -n (?P<numpe>[0-9]+)',
            cmd
        )
        if numpe_match is None:
            es = F"Cannot determine numpe from:'{cmd}'"
            raise ValueError(es)
        numpe = int(numpe_match.group('numpe'))
        self.data['numpe'].append(numpe)

        self._parsenstore(kwargs.pop('output'))

    def _parsenstore(self, outl):
        lines = [x.rstrip() for x in outl]
        parser = MPI1Parser(lines)
        parser.parse()
        '''
        for line in lines:
            if line.startswith('CG (H1) total time:'):
                self.data['cgh1'].append(parsel(line))
                continue
            if line.startswith('CG (L2) total time:'):
                self.data['cgl2'].append(parsel(line))
                continue
        '''

    def run(self):
        # Generate the prun commands for the specified job sizes.
        pruns = experiment.generate(
            F'{self.config.args.prun} -n {{}}',
            # TODO(skg)
            [2]
        )
        # Generate the run commands for the given benchmarks.
        cmds = [os.path.join(self.config.args.bin_dir, b.strip())
                for b in self.config.args.benchmarks.split(',')]

        logger.emlog('# Starting Runs...')

        for prun in pruns:
            for cmd in cmds:
                logger.log('')
                container.prun(prun, cmd, postaction=self.post_action)

    def report(self):
        logger.emlog(F'# {experiment.name()} Report')
        return

        header = [
            'numpe',
            'tottime',
            'cgh1',
            'cgl2'
        ]

        data = zip(
            self.data['numpe'],
            self.data['tottime'],
            self.data['cgh1'],
            self.data['cgl2']
        )

        table = utils.Table()
        csvfname = self.config.args.csv_output
        with open(csvfname, 'w', newline='') as csvfile:
            dataw = csv.writer(csvfile)
            dataw.writerow(header)
            table.addrow(header, withrule=True)
            for numpe, t, cgh1, cgl2 in data:
                row = [numpe, t, cgh1, cgl2]
                dataw.writerow(row)
                table.addrow(row)

        # metadata.add_asset(metadata.FileAsset(csvfname))
        table.emit()


class Program:
    def __init__(self, argv):
        self.desc = 'bueno run script for IMB.'
        # Experiment configuration, data, and analysis.
        self.experiment = Experiment(Configuration(self.desc, argv))

    def run(self):
        self.experiment.run()
        # self.experiment.report()


def main(argv):
    Program(argv).run()
