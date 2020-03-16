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
from bueno.public import metadata
from bueno.public import utils

from collections import defaultdict

import csv
import os
import re

# TODO(skg) Make a verify function.
def build_parser(bname, numpe):
    if bname in ['IMB-MPI1',
                 'IMB-P2P',
                 'IMB-MT',
                 'IMB-EXT',
                 'IMB-RMA',
                 'IMB-IO',  # Disabled by default.
                 'IMB-NBC'  # Disabled by default.
                 ]:
        return BenchmarkOutputParser(bname, numpe)
    raise RuntimeError(F'Unrecognized benchmark name: {bname}')


class DataNamer:
    def __init__(self):
        # Key/counter
        self.datai = defaultdict(int)

    def generate(self, name_prefix):
        kid = self.datai[name_prefix]
        self.datai[name_prefix] += 1
        return F'{name_prefix}-runid:{kid}'

class BenchmarkOutputParser:
    def __init__(self, name):
        self.name = name
        self._bmdata = BenchmarkData(name)
        self._lines = None
        self._nlines = 0
        self._lineno = 0

    def _line(self, advl):
        if self._lineno == self._nlines:
            return None
        line = self._lines[self._lineno]
        if advl:
            self.advl()
        return line

    def advl(self):
        self._lineno += 1

    def rewindl(self, nlines):
        self._lineno -= nlines
        if self._lineno < 0:
            raise RuntimeError('Cannot rewind past zero.')

    def line(self):
        return self._line(False)

    def nextl(self):
        return self._line(True)

    def _parse_start(self, lines):
        self._lines = lines
        self._nlines = len(lines)
        self._lineno = 0

    def _bmname_parse(self):
        line = self.nextl()
        match = re.search('# Benchmarking' + r' (?P<bmname>[A-Za-z_]+)', line)
        if match is None:
            return None
        return match.group('bmname')

    def _numpe_numt_parse(self):
        # Convenience function that deals with numt.
        def _numt(match):
            numt = match.group('numt')
            # numt not specified, so default to 1.
            if numt is None:
                return 1
            return int(numt)

        line = self.nextl()
        # No executions.
        if line.startswith('# NO SUCCESSFUL EXECUTIONS'):
            self.advl()
            return (None, None)
        # If we are here, then we have something to parse.
        res = '# #processes = ' \
              r'(?P<numpe>[0-9]+)( \(threads: (?P<numt>[0-9]+)\))?'
        match = re.search(res, line)
        # Assume this subparser is called only in the correct context.
        if match is None:
            raise RuntimeError(F"Expected '# #processes', got:\n{line}")
        numpe = int(match.group('numpe'))
        numt = _numt(match)
        return (numpe, numt)

    def _window_size_parse(self):
        if self.line().startswith('#-'):
            # Eat the next line, No window size for this one.
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
            (numpe, numt) = self._numpe_numt_parse()
            # Nothing left to parse.
            if numpe is None:
                continue
            bdargs = {
                'name': bmname,
                'numpe': numpe,
                'numt': numt,
                'window_size': self._window_size_parse(),
                'mode': self._mode_parse(),
                'metrics': self._metrics_parse(),
                'stats': self._stats_parse()
            }
            self._bmdata.add(BenchmarkDatum(**bdargs))

    def data(self):
        return self._bmdata


class BenchmarkDatum:
    def __init__(self, name, numpe, numt, window_size, mode, metrics, stats):
        self.name = name
        self.numpe = numpe
        self.numt = numt
        self.window_size = window_size
        self.mode = mode
        self.metrics = metrics
        self.stats = stats

    def tabulate(self, name):
        logger.log(F"#{'-'*79}")
        logger.log(F"# name: {self.name}")
        logger.log(F"# numpe: {self.numpe}")
        logger.log(F"# numt: {self.numt}")
        logger.log(F"# window_size: {self.window_size}")
        logger.log(F"# mode: {self.mode}")
        logger.log(F"#{'-'*79}")

        table = utils.Table()
        csvfname = F'{name}.csv'
        with open(csvfname, 'w', newline='') as csvfile:
            dataw = csv.writer(csvfile)
            dataw.writerow(self.metrics)
            table.addrow(self.metrics, withrule=True)
            for row in self.stats:
                table.addrow(row)
                dataw.writerow(row)
            table.emit()
            logger.log('\n')

        metadata.add_asset(metadata.FileAsset(csvfname))


class BenchmarkData:
    def __init__(self, name):
        self.name = name
        self.data = list()

    def add(self, bmdatum):
        self.data.append(bmdatum)

    def tabulate(self):
        for d in self.data:
            d.tabulate(self.name)


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
        benchmarks = 'IMB-MT, IMB-MT'
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
        # Set the experiment's name.
        experiment.name(self.config.args.name)
        # The instance responsible for naming data.
        self.data_namer = DataNamer()
        # Data container.
        self.data = {
            'commands': list(),
            'bmdata': list()
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
        udata = kwargs.pop('user_data')
        app = udata.pop('app')
        numpe = udata.pop('numpe')

        # TODO(skg) Verify that the app is one we recognize.
        name = self.data_namer.generate(F'{app}-numpe:{numpe}')
        parser = BenchmarkOutputParser(name)
        lines = [x.rstrip() for x in kwargs.pop('output')]
        parser.parse(lines)

        self.data['commands'].append(kwargs.pop('command'))
        self.data['bmdata'].append(parser.data())

    def run(self):
        # TODO(skg) Auto-generate.
        numpes = [1, 2]
        # Generate list of apps for the given benchmarks.
        apps = [b.strip() for b in self.config.args.benchmarks.split(',')]

        logger.emlog('# Starting Runs...')

        for app in apps:
            for numpe in numpes:
                logger.log('')
                container.prun(
                    # TODO(skg) Make -n an option.
                    F'{self.config.args.prun} -n {numpe}',
                    os.path.join(self.config.args.bin_dir, app),
                    postaction=self.post_action,
                    user_data={'app': app, 'numpe': numpe}
                )

    def report(self):
        logger.emlog(F'# {experiment.name()} Report')

        cmddata = zip(
            self.data['commands'],
            self.data['bmdata']
        )
        for cmd, bmdata in cmddata:
            logger.log(F"#{'#'*79}")
            logger.log(F"#{'#'*79}")
            logger.log(F'# {cmd}')
            logger.log(F"#{'#'*79}")
            logger.log(F"#{'#'*79}\n")
            bmdata.tabulate()


class Program:
    def __init__(self, argv):
        self.desc = 'bueno run script for IMB.'
        # Experiment configuration, data, and analysis.
        self.experiment = Experiment(Configuration(self.desc, argv))

    def run(self):
        self.experiment.run()
        self.experiment.report()


def main(argv):
    Program(argv).run()
