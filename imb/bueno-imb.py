#
# Copyright (c) 2019-2020 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import utils

import csv
import os
import re


def build_parser(bname):
    if bname in ['IMB-MPI1',
                 'IMB-P2P',
                 'IMB-MT',
                 'IMB-EXT',
                 'IMB-RMA',
                 'IMB-IO',  # Disabled by default.
                 'IMB-NBC'  # Disabled by default.
                 ]:
        return BenchmarkOutputParser(bname)

    raise RuntimeError(F'Unrecognized benchmark name: {bname}')


class BenchmarkOutputParser:
    def __init__(self, name):
        self.name = name
        self.lines = None
        self.nlines = 0
        self.lineno = 0
        self.bmdata = BenchmarkData(name)

    def _line(self, advl):
        if self.lineno == self.nlines:
            return None
        line = self.lines[self.lineno]
        if advl:
            self.advl()
        return line

    def advl(self):
        self.lineno += 1

    def rewindl(self, nlines):
        self.lineno -= nlines
        if self.lineno < 0:
            raise RuntimeError('Cannot rewind past zero.')

    def line(self):
        return self._line(False)

    def nextl(self):
        return self._line(True)

    def data(self):
        return self.bmdata

    def _parse_start(self, lines):
        self.lines = lines
        self.nlines = len(lines)
        self.lineno = 0

    def _bmname_parse(self):
        line = self.nextl()
        match = re.search('# Benchmarking' + r' (?P<bmname>[A-Za-z_]+)', line)
        if match is None:
            return None
        return match.group('bmname')

    # TODO(skg) Add threading.
    def _numpe_parse(self):
        line = self.nextl()
        match = re.search('# #processes = ' + r'(?P<numpe>[0-9]+)', line)
        # Assume this subparser is called only in the correct context.
        if match is None:
            raise RuntimeError(F"Expected '# #processes', got:\n{line}")
        return int(match.group('numpe'))

    def _window_size_parse(self):
        if self.line().startswith('#-'):
            # Eat the next line.
            self.advl()
            return None
        line = self.nextl()
        match = re.search('# window_size = ' + r'(?P<winsize>[0-9]+)', line)
        # Assume this subparser is called only in the correct context.
        if match is None:
            raise RuntimeError(F"Expected '# window_size', got:\n{line}")
        # Eat the next line.
        self.advl()
        return int(match.group('winsize'))


    def _mode_parse(self):
        line = self.nextl()
        if line is None:
            raise RuntimeError(F"Expected text, but got None.")
        # There is a chance this is a mode block.
        match = None
        if not line.startswith('#'):
            self.rewindl(1)
            return None
        else:
            line = self.nextl()
            match = re.search('#    MODE: ' + r'(?P<mode>[A-Z-]+)', line)
            # Assume this subparser is called only in the correct context.
            if match is None:
                self.rewindl(2)
                return None
        # Eat the next line.
        self.advl()
        return match.group('mode')

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

    def parse(self, lines):
        self._parse_start(lines)
        while self.line() is not None:
            bmname = self._bmname_parse()
            if bmname is None:
                continue
            bdargs = {
                'name': bmname,
                'numpe': self._numpe_parse(),
                'window_size': self._window_size_parse(),
                'mode': self._mode_parse(),
                'metrics': self._metrics_parse(),
                'stats': self._stats_parse()
            }

            self.bmdata.add(BenchmarkDatum(*bdargs))
            print(F"name:        {bdargs['name']}")
            print(F"numpe:       {bdargs['numpe']}")
            print(F"window_size: {bdargs['window_size']}")
            print(F"mode:        {bdargs['mode']}")
            print(F"metrics:     {bdargs['metrics']}")
            print(F"stats:       {bdargs['stats']}\n")


class BenchmarkDatum:
    def __init__(self, name, numpe, window_size, mode, metrics, stats):
        self.name = name
        self.numpe = numpe
        self.window_size = window_size
        self.mode = mode
        self.metrics = metrics
        self.stats = stats


class BenchmarkData:
    def __init__(self, name):
        self.name = name
        self.data = dict()

    def add(self, bmdatum):
        self.data[F'{bmdatum.name}-{bmdatum.numpe}'] = bmdatum


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
        benchmarks = 'IMB-MPI1, IMB-P2P, IMB-MT, IMB-EXT'
        benchmarks = 'IMB-MT'
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
        # TODO(skg) Auto get name. Consider adding pass user args.
        parser = build_parser('IMB-IO')
        lines = [x.rstrip() for x in outl]
        parser.parse(lines)

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
