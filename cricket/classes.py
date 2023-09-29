import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import chain, zip_longest

from functions import List, attrlister, zero_freqs


class PlayerMethods:
    def __repr__(self):
        return type(self).__name__ + '({})'.format(self)

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == getattr(other, 'name', other)


class Role(PlayerMethods):
    def __init__(self, player, role):
        self.name = player.name
        self.style = getattr(player, role + '_style')
        self.freqs = {k: defaultdict(zero_freqs) for k in ('balls', 'style', 'opponent')}

    def __repr__(self):
        return super().__repr__() + ': {}'.format(self.score)

    def __floordiv__(self, other):
        return (self.balls - 1) // other

    def __lt__(self, other):
        if self.balls and other.balls:
            return self._score() < other._score()
        return self.balls < other.balls

    def __add__(self, other):
        new = deepcopy(self)
        for attr in self._attrs:
            setattr(new, attr, getattr(self, attr) + getattr(other, attr))

        return new


class Batter(Role):
    def __init__(self, player, *positions):
        super().__init__(player, 'batting')
        self.position, self.true_position = positions
        self.runs = self.balls = self.fours = self.sixes = 0
        self.dismissal = 'Not Out'

    @property
    def out(self):
        return self.dismissal != 'Not Out'

    @property
    def strike_rate(self):
        return '{:.2f}'.format(self.runs / (self.balls + 1e-5) * 100)

    @property
    def score(self):
        return '{}{} ({})'.format(self.runs, '' if self.out else '*', self.balls)

    def _score(self):
        return (self.runs, - self.out, self.balls)

    def __iadd__(self, other):
        self.runs += int(other)
        self.balls += 'wd' not in str(other)

        if 'non_boundary' not in getattr(other, 'data', {}).get('runs', {}):
            self.fours += int(other) == 4
            self.sixes += int(other) == 6

        return self


class Bowler(Role):
    def __init__(self, player):
        super().__init__(player, 'bowling')
        self.balls = self.maidens = self.runs = self.wickets = self.extras = 0
        self.spells = []

    @property
    def overs(self):
        return self.balls // 6 + (self.balls % 6 / 10 if self.balls % 6 else 0)

    @property
    def economy(self):
        return '{:.2f}'.format(self.runs / (self.balls / 6 + 1e-5))

    @property
    def score(self):
        return '{} - {} ({})'.format(self.wickets, self.runs, self.overs)

    def _score(self):
        return (self.wickets, - self.runs, self.overs)

    def __iadd__(self, other):
        balls = str(other[-1])[1:] not in ('nb', 'wd')
        runs = abs(other[-1]) if str(other[-1])[1:] not in ('b', 'lb') else 0
        wickets = other[-1] == 'W'
        extras = 1 if 'nb' in str(other[-1]) else abs(other[-1]) if 'wd' in str(other[-1]) else 0

        if len(other.bowlers) == 1 and abs(other) == 6:
            maidens = not sum(abs(ball) for ball in other if str(ball)[1:] not in ('b', 'lb'))

        for attr, value in locals().items():
            if attr in ('balls', 'maidens', 'runs', 'wickets', 'extras'):
                setattr(self, attr, getattr(self, attr) + value)

        self.spells[-1] += [balls / 6, locals().get('maidens', 0), runs, wickets]

        return self


class MatchMethods:
    def __init__(self, index, teams, pdb):
        self.index = index
        self.teams = teams
        self.squads = {team: deepcopy(pdb[team]) for team in teams}
        self.players = {team: List(squad.starting) for team, squad in self.squads.items()}

        self.innings = []

    @property
    def result(self):
        if 'winner' in self.outcome:
            if 'innings' in self.outcome['by']:
                margin = 'an innings and {} runs'.format(self.outcome['by']['runs'])
            elif 'runs' in self.outcome['by']:
                margin = '{} runs'.format(self.outcome['by']['runs'])
            else:
                margin = '{} wickets'.format(self.outcome['by']['wickets'])

            return self.outcome['winner'] + ' won by ' + margin
        else:
            return self.outcome['result']

    @property
    def summary(self):
        return self._summary()

    def _summary(self, window=5):
        display = window - len(self)
        summary = []

        for inn in self:
            half = ('1st' if inn.index < 2 else '2nd') + ' Innings'
            score = '{} ({})'.format(*inn.bat_card.iloc[-1, [2, 3]])
            scores = [attrlister(sorted(getattr(inn, attr), reverse=True)[:display], 'name', 'score')
                      for attr in ('batters', 'bowlers')]
            summary.extend([('',) * 4, (inn.batting_team, '', half, score),
                            *(l1 + l2 for l1, l2 in zip_longest(*scores, fillvalue=('', '')))])

        return pd.DataFrame(summary, range(1, len(summary) + 1), [self.teams[0], 'vs', self.teams[1], self.index])

    def __repr__(self):
        return type(self).__name__ + '({}, {} vs {}): {}'.format(self.index, *self.teams, self.outcome)

    def __len__(self):
        return len(self.innings)

    def __getitem__(self, index):
        return self.innings[index]


class InningMethods:
    def __init__(self, mat, batting_idx):
        self.index = len(mat)
        self.batting_team = mat.teams[batting_idx]
        self.bowling_team = mat.teams[1 - batting_idx]

        self.batters = List()
        self.bowlers = List()
        self.fielders = mat.players[self.bowling_team].copy()

        for fielder in self.fielders:
            fielder.init_fielding(mat.index, self.index)

        try:
            self.keeper = next(player for player in reversed(self.fielders) if 'keeper' in str(player.role))
            self.fielders.remove(self.keeper)
        except StopIteration:
            self.keeper = None

        self.overs = []
        self.score = np.zeros(2, int)
        self.freqs = {'overs': defaultdict(zero_freqs),
                      'extras': {k1: {k2: Counter() for k2 in ('nb', 'wd', 'lb', 'b')} for k1 in 'FS'},
                      'dismissals': {k: Counter() for k in 'FS'},
                      'catches': Counter(),
                      'run_outs': Counter()}

    @property
    def scorecard(self):
        card = pd.DataFrame([[''] * 6] + [str(over).split() for over in self]).rename_axis('Over').fillna('')
        card.drop(0, inplace=True)
        card.columns += 1
        card.insert(0, 'Bowler', ['/'.join(bowler.name for bowler in over.bowlers) for over in self])
        card['Score'] = attrlister(self, 'score')

        return card

    @property
    def bat_card(self):
        stats = attrlister(self.batters, 'name', 'dismissal', 'runs', 'balls', 'fours', 'sixes')
        card = pd.DataFrame(stats, columns=['Name', '', 'R', 'B', '4s', '6s']).set_index('Name')
        card['S/R'] = (card['R'] / (card['B'] + 1e-5) * 100).apply('{:.2f}'.format)

        try:
            score = str(self.score[0]) if sum(1 for batter in self.batters if batter.out) == 10 else self[-1].score
            index = self[-1].index + abs(self[-1]) / 10
            overs = '{} ov'.format(index if abs(self[-1]) % 6 else round(index))
            run_rate = 'RR: {:.2f}'.format(self.score[0] / (int(index) + index % 1 / 0.6 + 1e-5))
            extras = 'Extras: {}'.format(self.score[0] - sum(card['R']))
            card.loc[self.batting_team] = ['', '', score, overs, run_rate, extras]
        except IndexError:
            card.loc[self.batting_team] = ['', '', '0 - 0', '0 ov', 'RR: 0.00', 'Extras: 0']

        return card

    @property
    def bowl_card(self):
        stats = attrlister(self.bowlers, 'name', 'balls', 'overs', 'maidens', 'runs', 'wickets', 'extras')
        card = pd.DataFrame(stats, columns=['Name', 'B', 'O', 'M', 'R', 'W', 'Extras']).set_index('Name')
        card['Econ'] = (card['R'] / (card['B'] + 1e-5) * 6).apply('{:.2f}'.format)
        card.drop('B', axis=1, inplace=True)
        card.loc[self.bowling_team] = list(self.bat_card.iloc[-1])

        return card

    @property
    def fow(self):
        return ['{} ({}, {} ov)'.format(ball.score, ball.batter if ball.batter.out else ball.non_striker, ball.index)
                for ball in self.wickets() if 'W' in str(ball)]

    @property
    def pships(self):
        try:
            pships = attrlister(self.wickets(), 'pship')
            last = self[-1][-1] if self[-1] else self[-2][-1]
            if last.pship not in pships:
                pships.append(last.pship)
            return pships
        except IndexError:
            return []

    def balls(self):
        return list(chain(*self))

    def wickets(self):
        return [ball for ball in self.balls() if 'W' in str(ball) or 'wickets' in getattr(ball, 'd', {})]

    def update(self, at_crease, striker, bowler, pship, mat, *args):
        over = *_, ball = self[-1]
        batter = at_crease[striker]
        batter += ball
        bowler += over

        if 'W' in str(ball) or 'wickets' in getattr(ball, 'data', {}):
            self._get_dismissal(bowler, pship, mat.index, at_crease, striker, *args)
            pship[:] = 0

        try:
            self._next_striker(striker, args[-1])
        except AttributeError:
            pass

        for d, k in zip((self.freqs['overs'], *batter.freqs.values(), *bowler.freqs.values()),
                        (self // 60, batter // 20, bowler.style, bowler.name, bowler // 30, batter.style, batter.name)):
            if ball == 'W':
                d[k][7] += 1
            elif int(ball) > 6:
                d[k][int(ball) - 4] += 1
            elif 'wd' not in str(ball):
                d[k][int(ball)] += 1

        if str(ball)[1:] in ('nb', 'wd', 'lb', 'b'):
            self.freqs['extras'][bowler.style[-1]][ball.value[1:]][abs(ball)] += 1

        ball.batter = deepcopy(batter)
        ball.non_striker = deepcopy(at_crease[1 - striker])
        ball.bowler = over.bowlers[-1] = deepcopy(bowler)

    def get_dismissal(self, mode, bowler, fielders, match_idx):
        if 'retired' not in mode and mode != 'run out':
            self.freqs['dismissals'][bowler.style[-1]][mode] += 1

        if mode == 'bowled':
            return 'b {}'.format(bowler)
        elif mode == 'lbw':
            return 'lbw b {}'.format(bowler)
        elif mode == 'caught':
            if not isinstance(fielders[0], str):
                only_fielders = self.fielders.copy()
                only_fielders.remove(bowler)
                self.freqs['catches'][min(8, only_fielders.index(fielders[0]))] += 1
                fielders[0].innings[match_idx]['fielding'][self.index]['catches'] += 1
                return 'c {} b {}'.format(fielders[0], bowler)
            return 'c sub ({}) b {}'.format(fielders[0], bowler)
        elif mode == 'caught behind':
            if not isinstance(fielders[0], str):
                fielders[0].innings[match_idx]['fielding'][self.index]['catches'] += 1
                return 'c {} b {}'.format(fielders[0], bowler)
            return 'c sub ({}) b {}'.format(fielders[0], bowler)
        elif mode == 'caught and bowled':
            self.fielders[bowler].innings[match_idx]['fielding'][self.index]['catches'] += 1
            return 'c & b {}'.format(bowler)
        elif mode == 'stumped':
            if not isinstance(fielders[0], str):
                fielders[0].innings[match_idx]['fielding'][self.index]['stumpings'] += 1
                return 'st {} b {}'.format(fielders[0], bowler)
            return 'st sub ({}) b {}'.format(fielders[0], bowler)
        elif mode == 'run out':
            self.freqs['run_outs'][abs(self[-1][-1])] += 1
            real_fielders = [fielder for fielder in fielders if not isinstance(fielder, str)]
            if len(real_fielders) == 1:
                real_fielders[0].innings[match_idx]['fielding'][self.index]['run outs'] += 1
            else:
                for fielder in real_fielders:
                    if fielder != self.keeper:
                        fielder.innings[match_idx]['fielding'][self.index]['run outs'] += 1
            if len(fielders):
                return 'run out ({})'.format('/'.join(map(str, fielders)))
            return 'run out'
        elif 'retired' in mode:
            return 'retired hurt'
        elif mode == 'hit wicket':
            return 'hit wicket b {}'.format(bowler)
        else:
            raise ValueError('unseen mode: ' + mode)

    def new_batter(self, player, mat):
        batter = Batter(player, len(self.batters), mat.players[self.batting_team].index(player))
        mat.players[self.batting_team][batter].innings[mat.index]['batting'][self.index] = batter
        self.batters.append(batter)

        return batter

    def new_bowler(self, player, mat):
        bowler = Bowler(player)
        mat.players[self.bowling_team][bowler].innings[mat.index]['bowling'][self.index] = bowler
        self.bowlers.append(bowler)

        return bowler

    def __repr__(self):
        return type(self).__name__ + '({}): {} - {}, {}'.format(self.index, *self.score, self.bat_card.iloc[-1, 3])

    def __len__(self):
        return len(self.overs)

    def __getitem__(self, index):
        try:
            return self.overs[index]
        except TypeError:
            try:
                return self.overs[index[0]]
            except IndexError:
                return index[1]

    def __floordiv__(self, other): 
        return (6 * (len(self) - 1) + max(0, abs(self[-1]) - 1)) // other
