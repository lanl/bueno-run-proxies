#
# Copyright (c) 2019-2020 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
bueno run script for the IMB suite.
'''

import csv
import io
import os
import re

from collections import defaultdict

from bueno.public import container
from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import utils


class Benchmark:
    @staticmethod
    def available():
        return ['IMB-MPI1',
                'IMB-P2P',
                'IMB-MT',
                'IMB-EXT',
                'IMB-RMA',
                'IMB-IO',
                'IMB-NBC']

    @staticmethod
    def recognized(name):
        return name in Benchmark.available()

    @staticmethod
    def default_list():
        # Disabled by default.
        dbd = ['IMB-IO', 'IMB-NBC']
        return ','.join([x for x in Benchmark.available() if x not in dbd])


class DataLabel:
    def __init__(self, name, numpe, generation):
        self.name = str(name)
        self.numpe = str(numpe)
        self.generation = str(generation)


class DataLabeler:
    def __init__(self):
        # Key/counter
        self.datai = defaultdict(int)

    def label(self, name, numpe):
        key = F'{name}-{numpe}'
        gen = self.datai[key]
        self.datai[key] += 1
        return DataLabel(name, numpe, gen)


class BenchmarkOutputParser:
    def __init__(self, label):
        self._bmdata = BenchmarkData(label)
        self._lines = None
        self._nlines = 0
        self._lineno = 0

    def _line(self, eatl):
        if self._lineno == self._nlines:
            return None
        line = self._lines[self._lineno]
        if eatl:
            self.eatl()
        return line

    def eatl(self):
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
                return None
            return int(numt)

        line = self.nextl()
        # No executions.
        if line.startswith('# NO SUCCESSFUL EXECUTIONS'):
            self.eatl()
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
        def bail():
            line = self.line()
            if line.startswith('#-'):
                return True
            match = re.match(
                r'# \(\s*[0-9]+ additional process(?:es)? '
                r'waiting in MPI_Barrier\)',
                line
            )
            if match:
                # Eat the line. We are dealing with a waiting line.
                self.eatl()
                return True
            return False
        if bail():
            self.eatl()
            return None
        line = self.nextl()
        match = re.search('# window_size = ' + r'(?P<winsize>[0-9]+)', line)
        # Assume this subparser is called only in the correct context.
        if match is None:
            raise RuntimeError(F"Expected '# window_size', got:\n{line}")
        # Eat the next line.
        self.eatl()
        return int(match.group('winsize'))

    def _mode_parse(self):
        line = self.nextl()
        match = re.match(r'^#$', line)
        if match is None:
            self.rewindl(1)
            return None
        # There is a chance this is a mode block.
        match = re.search('#    MODE: ' + r'(?P<mode>[A-Z-]+)', self.nextl())
        if match is None:
            self.rewindl(2)
            return None
        # Eat the next line.
        self.eatl()
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
            raise RuntimeError('Expected run statistics, but found none.')
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

    def tabulate(self, label):
        logger.log(F"#{'-'*79}")
        logger.log(F"# name: {self.name}")
        logger.log(F"# numpe: {self.numpe}")
        logger.log(F"# numt: {self.numt}")
        logger.log(F"# window_size: {self.window_size}")
        logger.log(F"# mode: {self.mode}")
        logger.log(F"#{'-'*79}")

        table = utils.Table()
        sio = io.StringIO(newline=None)
        dataw = csv.writer(sio)

        metad = [('numt', self.numt),
                 ('window_size', self.window_size),
                 ('mode', self.mode)]

        # Write metadata header to csv file. Is this the best way to do this?
        for coll in metad:
            key = coll[0]
            val = coll[1]
            if not val:
                continue
            dataw.writerow([F'##{key}', val])

        dataw.writerow(self.metrics)
        table.addrow(self.metrics, withrule=True)
        for row in self.stats:
            table.addrow(row)
            dataw.writerow(row)
        table.emit()
        logger.log('\n')

        csvfname = F'{self.name}'
        csvfname += F'-{self.numpe}PE'
        if self.mode is not None:
            csvfname += F'-{self.mode.lower()}'
        csvfname += '.csv'

        opath = os.path.join(
            label.name,
            F'numpe-{label.numpe}',
            F'runid-{label.generation}'
        )
        metadata.add_asset(metadata.StringIOAsset(sio, csvfname, opath))


class BenchmarkData:
    def __init__(self, label):
        self.label = label
        self.data = list()

    def add(self, bmdatum):
        self.data.append(bmdatum)

    def tabulate(self):
        for datum in self.data:
            datum.tabulate(self.label)


class Configuration(experiment.CLIConfiguration):
    def __init__(self, desc, argv):
        super().__init__(desc, argv)
        # Get and process any arguments provided. Do this as early as possible
        # to see an up-to-date version of the config.
        if not utils.emptystr(self.args.input):
            experiment.readgs(self.args.input, self)

    def addargs(self):
        self.argparser.add_argument(
            '--benchmarks',
            type=str,
            metavar='B1,B2,...',
            help='Comma-delimited list of IMB benchmarks to run.'
                 ' (default: %(default)s)'
                 F" (choices: {','.join(Benchmark.available())})",
            required=False,
            default=Configuration.Defaults.benchmarks
        )

        self.argparser.add_argument(
            '--bin-dir',
            type=str,
            metavar='DIR',
            help='Specifies the base directory of the IMB binaries.'
                 ' (default: %(default)s)',
            required=False,
            default=Configuration.Defaults.bin_dir
        )

        self.argparser.add_argument(
            '-d', '--description',
            type=str,
            metavar='DESC',
            help='Describes the experiment.'
                 ' (default: %(default)s)',
            required=False,
            default=Configuration.Defaults.description
        )

        self.argparser.add_argument(
            '-i', '--input',
            type=str,
            metavar='INP',
            help='Specifies the path to an experiment input.',
            required=False
        )

        self.argparser.add_argument(
            '--name',
            type=str,
            help='Names the experiment.'
                 ' (default: %(default)s)',
            required=False,
            default=Configuration.Defaults.experiment_name
        )
        # Add pre-canned options to deal with experiment.runcmds() input.
        experiment.cli_args_add_runcmds_options(
            self,
            opt_required=False,
            opt_default=Configuration.Defaults.rcmds
        )

    class Defaults:
        benchmarks = Benchmark.default_list()
        bin_dir = '/IMB'
        description = 'Intel MPI Benchmarks'
        experiment_name = 'imb'
        rcmds = (0, 2, 'srun -n %n', 'nidx + 1')


class Experiment:
    def __init__(self, config):
        # The experiment configuration.
        self.config = config
        # Set the experiment's name.
        experiment.name(self.config.args.name)
        # The instance responsible for naming data.
        self.data_labeler = DataLabeler()
        # Data container.
        self.data = {
            'commands': list(),
            'bmdata': list()
        }
        # Emit program configuration to terminal.
        self.emit_conf()
        # Add assets to collection of metadata.
        self.add_assets()

    def add_assets(self):
        if not utils.emptystr(self.config.args.input):
            metadata.add_asset(metadata.FileAsset(self.config.args.input))

    def emit_conf(self):
        pcd = dict()
        pcd['Program'] = vars(self.config.args)
        utils.yamlp(pcd, 'Program')

    def post_action(self, **kwargs):
        udata = kwargs.pop('user_data')
        app = udata.pop('app')
        numpe = udata.pop('numpe')

        label = self.data_labeler.label(app, numpe)
        parser = BenchmarkOutputParser(label)
        lines = [x.rstrip() for x in kwargs.pop('output')]
        parser.parse(lines)

        self.data['commands'].append(kwargs.pop('command'))
        self.data['bmdata'].append(parser.data())

    def run(self):
        def _get_numpe(prun):
            numpe_match = re.search(r'\s+-n\s?(?P<numpe>[0-9]+)', prun)
            if numpe_match is None:
                estr = F"Cannot determine numpe from:'{prun}'"
                raise ValueError(estr)
            return int(numpe_match.group('numpe'))
        # Generate the run commands for the given experiment.
        rcmd = self.config.args.runcmds
        pruns = experiment.runcmds(rcmd[0], rcmd[1], rcmd[2], rcmd[3])
        # Generate list of apps for the given benchmarks.
        apps = [b.strip() for b in self.config.args.benchmarks.split(',')]
        logger.emlog('# Starting Runs...')
        for app in apps:
            if not Benchmark.recognized(app):
                logger.emlog(F'# SKIPPING UNRECOGNIZED BENCHMARK: {app}')
                continue
            for prun in pruns:
                logger.log('')
                container.prun(
                    F'{prun}',
                    os.path.join(self.config.args.bin_dir, app),
                    postaction=self.post_action,
                    user_data={'app': app, 'numpe': _get_numpe(prun)}
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

# vim: ft=python ts=4 sts=4 sw=4 expandtab
