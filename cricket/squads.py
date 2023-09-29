import pandas as pd
from collections import defaultdict
from functools import reduce
from itertools import chain
from operator import add, itemgetter

from functions import Float, attrlister
from classes import PlayerMethods


class Player(PlayerMethods):
    def __init__(self, name, role, styles):
        self.name = name
        self.role = role
        self.batting_style, self.bowling_style = styles
        self.innings = defaultdict(self._init_innings)

    @property
    def batting(self):
        innings = self._get_innings('batting')

        try:
            runs, outs, balls = self._sum_innings(innings, 'runs', 'out', 'balls')
            HS = max(innings).score
        except ValueError:
            runs = outs = balls = 0
            HS = ''
    
        return {'Mat': len(self.innings),
                'Inn': len(innings),
                'NO': len(innings) - outs,
                'R': runs,
                'B': balls,
                'HS': HS,
                'Avg': round(Float(runs) / outs, 2),
                'S/R': round(Float(runs) / balls * 100, 2),
                '100s': sum(1 for inning in innings if inning.runs >= 100),
                '50s': sum(1 for inning in innings if 50 <= inning.runs < 100),
                '4s': sum(attrlister(innings, 'fours')),
                '6s': sum(attrlister(innings, 'sixes'))}

    @property
    def bowling(self):
        innings = self._get_innings('bowling')
        matches = [reduce(add, match.values()) for match in self['bowling'].values()]

        try:
            wickets, runs, balls = self._sum_innings(innings, 'wickets', 'runs', 'balls')
            BBI = max(innings).score
            BBM = max(matches).score
        except ValueError:
            wickets = runs = balls = 0
            BBI = BBM = ''

        return {'Mat': len(self.innings),
                'Inn': len(innings),
                'O': balls // 6 + (balls % 6 * 0.1 if balls % 6 else 0),
                'M': sum(attrlister(innings, 'maidens')),
                'R': runs,
                'W': wickets,
                'BBI': BBI,
                'BBM': BBM,
                'Avg': round(Float(runs) / wickets, 2),
                'Econ': round(Float(runs) / balls * 6, 2),
                'S/R': round(Float(balls) / wickets, 2),
                '5WI': sum(1 for inning in innings if inning.wickets >= 5),
                '10WM': sum(1 for match in matches if match.wickets >= 10)}

    @property
    def fielding(self):  # change keys
        innings = self._get_innings('fielding')

        return {'Mat': len(self.innings),
                'Inn': len(innings),
                **{k: sum(v) for k, v in pd.DataFrame(innings, columns=('catches','stumpings','run outs')).items()}}

    def init_fielding(self, mat_idx, inn_idx):
        self.innings[mat_idx]['fielding'][inn_idx] = {k: 0 for k in ('catches', 'stumpings', 'run outs')}

    def _init_innings(self):
        return {k: {} for k in ('batting', 'bowling', 'fielding')}

    def _get_innings(self, index):
        return list(chain.from_iterable(inns.values() for inns in self[index].values()))

    def _sum_innings(self, innings, *attrs):
        return map(sum, zip(*attrlister(innings, *attrs)))

    def __getitem__(self, index):
        return {mat_idx: inns[index] for mat_idx, inns in self.innings.items() if inns[index]}


class Squad:
    def __init__(self, team, info):
        self.team = team
        self.players = {name: Player(name, role, styles) for name, (role, *styles, _, _) in info.iterrows()}
        self.first_XI = itemgetter(*info.index[info['starting'] == 1])(self)
        self.bowling_order = itemgetter(*info['bowling_order'].dropna())(self)

    @property
    def starting(self):
        return self.first_XI

    @property
    def batting(self):
        return self._get_stats('batting')

    @property
    def bowling(self):
        return self._get_stats('bowling')

    @property
    def fielding(self):
        return self._get_stats('fielding')

    def _get_stats(self, attr):
        return pd.DataFrame(attrlister(self, attr), self.players).rename_axis('Name')

    def __repr__(self):
        return type(self).__name__ + '({})'.format(self)

    def __str__(self):
        return self.team

    def __len__(self):
        return len(self.players)

    def __iter__(self):
        return self.players.values().__iter__()

    def __getitem__(self, index):
        return self.players[index]


if __name__ == '__main__':
    squads_info = pd.read_excel('squads.xlsx', sheet_name=None, index_col='name')
    pdb = {team: Squad(team, info) for team, info in squads_info.items()}
    teams = list(pdb)
