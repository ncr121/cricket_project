import shelve
import pandas as pd
from collections import Counter, defaultdict
from itertools import chain

from functions import attrlister, total_dicts
from loader import get_filenames
from cricsheet_match import RealSquad, RealMatch


def get_matches(pdb_name=None, mdb_name=None, fnames=None, start_date=None, end_date=None, all_teams=None):
    if all_teams == 'main':
        all_teams = {'Australia', 'Bangladesh', 'England', 'India', 'New Zealand', 'Pakistan', 'Sri Lanka',
                     'South Africa', 'West Indies'}

    if fnames is None:
        fnames = list(get_filenames(all_teams, start_date, end_date))

    if pdb_name is None:
        pdb = {}
    else:
        pdb = shelve.open(pdb_name, 'n')

    pdb.update({team: RealSquad(team) for team in all_teams})

    if mdb_name is None:
        mdb = {}
    else:
        mdb = shelve.open(mdb_name, 'n')

    for fname in fnames:
        try:
            m = RealMatch(fname, pdb)
            m.run(pdb)
            mdb[fname] = m
        except:
            return fname

    return pdb, mdb


def get_freqs(pdb, mdb, fdb_name):
    freqs = [{**{k: defaultdict(Counter) for k in ('batting', 'bowling', 'style', 'dismissals')},
              **{k: Counter() for k in ('overs', 'catches', 'run_outs')},
              **{k1: {k2: defaultdict(Counter) for k2 in 'FS'} for k1 in ('bowling', 'extras')}}
             for _ in range(5)]
    toss = Counter()

    for player in chain(*pdb.values()):
        for _, innings in player.innings.items():
            for i, inning in innings['batting'].items():
                for key in (i, 4):
                    freqs[key]['batting'][min(10, inning.true_position)].update(inning.freqs['balls'])
                    freqs[key]['style'][player.batting_style].update(inning.freqs['style'])

            for i, inning in innings['bowling'].items():
                for key in (i, 4):
                    (freqs[key]['bowling'][player.bowling_style[-1]]['part_time' if 'Batter' in player.role else 'main']
                      .update(inning.freqs['balls']))

    for match in mdb.values():
        toss[match.data['info']['toss']['decision']] += 1
        for inning in match:
            for key in (inning.index, 4):
                for k in ('overs', 'catches', 'run_outs'):
                    freqs[key][k].update(inning.freqs[k])

                for k, v in inning.freqs['dismissals'].items():
                    freqs[key]['dismissals'][k].update(v)

                for k1, v1 in inning.freqs['extras'].items():
                    for k2, v2 in v1.items():
                        freqs[key]['extras'][k1][k2].update(v2)

    for d in freqs:
        d['style'] = pd.DataFrame(d['style'])
        total_dicts(d)

    fdb = shelve.open(fdb_name, 'n')
    *fdb['innings'], fdb['total'] = freqs
    fdb['toss'] = toss
    fdb.close()

    return freqs


pdb_name = 'real_players'
mdb_name = 'real_matches'
dates = ['2019-08-01', '2021-06-23']
err = get_matches(pdb_name, mdb_name, 'main', *dates)

pdb = shelve.open(pdb_name, 'r')
mdb = shelve.open(mdb_name, 'r')
freqs = get_freqs(pdb, mdb, 'real_freqs')
stats = {attr: pd.concat(attrlister(pdb.values(), attr), keys=pdb) for attr in ('batting', 'bowling', 'fielding')}
