import os
import shelve
import numpy as np
import random as rd
from copy import deepcopy

from functions import rvg
from classes import InningMethods


class Inning(InningMethods):
    def __init__(self, mat):
        toss_idx = (['bat', 'field'].index(mat.toss['decision']) + mat.teams.index(mat.toss['winner'])) % 2
        batting_idx = (len(mat) + toss_idx + mat.follow_on) % 2
        super().__init__(mat, batting_idx)

        if self.index == 3:
            self.target = mat.target

        self.to_bat = mat.players[self.batting_team].copy()
        for _ in range(2):
            super().new_batter(self.to_bat.pop(0), mat)

        attack = [player for player in mat.squads[self.bowling_team].bowling_order if player in self.fielders]
        seamers, spinners = [[player for player in attack if player.bowling_style.endswith(x)] for x in 'FS']
        part_time = [player for player in set(self.fielders) - set(attack) if isinstance(player.bowling_style, str)]
        self.bowling_options = [attack, seamers, spinners, part_time]

        fdb = shelve.open(os.getcwd() + '\data\\real_freqs', 'r')
        self.loaded_freqs = {self.index: fdb['innings'][self.index], 'total': fdb['total']}

    def run(self, mat, pship=np.zeros((3,2),int)):
        while not self._end() and mat.sessions[0] < 5:
            if abs(self[-1, 6]) == 6:
                self._next_over(mat)
            self._next_ball(pship, mat)

    def rewind(self, index, mat, run=False):
        new = self.__class__(mat)
        pship = np.zeros((3, 2), int)

        for over in self[:index[0]]:
            new._rewind_over(over, pship, mat)

        if index[1] is not None:
            new._rewind_over(self[index[0]], pship, mat, index[1])

        if run:
            new.run(mat, pship)

        return new

    def _rewind_over(self, over, pship, mat, index=None):
        self._next_over(mat, over)
        for ball in over[:index]:
            self._next_ball(pship, mat, ball)

    def _end(self):
        return self.score[1] == 10 or self.score[0] >= getattr(self, 'target', float('inf'))

    def _next_over(self, match, default=None):
        if default is None:
            attack, seamers, spinners, part_time = self.bowling_options
            ends = [self.bowlers[over.bowlers[-1]] for over in self[-2:]]  # change
    
            if len(ends):
                ends[-1]._spell -= 1
    
            if len(ends) < 2:
                bowler = attack[len(ends)]
                super().new_bowler(bowler, match)
                ends.insert(0, self.bowlers[bowler])
                ends[0]._spell = rd.randint(5, 7)
            elif not ends[0]._spell:
                bowler = rd.choice(list(set(attack) - set(ends)))
                if bowler not in self.bowlers:
                    super().new_bowler(bowler, match)
    
                ends[0] = self.bowlers[bowler]
                ends[0]._spell = rd.randint(4, 7)

            bowler = ends[0]
        else:
            try:
                bowler = self.bowlers[default.bowlers[-1]]
            except ValueError:
                bowler = super().new_bowler(match.players[self.bowling_team][default.bowlers[-1]], match)
            bowler._spell = default.bowlers[-1]._spell
        
        self.overs.append(Over(bowler, self))  # super().append()

    def _next_ball(self, pship, mat, default=None):
        try:
            striker = (self[-1][-1] if self[-1] else self[-2][-1])._next_striker
        except IndexError:
            striker = 0

        at_crease = [batter for batter in self.batters if not batter.out]
        while len(at_crease) < 2:
            at_crease.append(super().new_batter(self.to_bat.pop(0), mat))

        bowler = self.bowlers[self[-1].bowlers[-1]]

        value = self._next_value(at_crease[striker], bowler) if default is None else default.value
        self[-1].append(Ball(value, at_crease, striker, pship, self))
        super().update(at_crease, striker, bowler, pship, mat, default)

    def _next_value(self, batter, bowler):
        weights = [[0.7, 0.3], [0.15, 0.5, 0.05, 0.1, 0.05, 0.1, 0.05]]

        probs = [[d['batting'][batter.true_position].get(batter // 20),
                  d['batting'][batter.true_position]['total'],
                  d['bowling'][bowler.style[-1]]['main'].get(bowler // 30),
                  d['bowling'][bowler.style[-1]]['main']['total'],
                  d['style'].get(batter.style, {}).get(bowler.style),
                  d['overs'].get(self // 60),
                  d['overs']['total']]
                 for d in self.loaded_freqs.values()]

        p = sum(w1 * sum(w2 * p2 / sum(p2) for w2, p2 in zip(weights[1], p1) if p2 is not None)
                for w1, p1 in zip(weights[0], probs))
        value, = rd.choices([*range(7), 'W'], p)

        total = self.loaded_freqs[self.index]['overs']['total']
        extras = self.loaded_freqs[self.index]['extras'][bowler.style[-1]]

        if extras['nb']['total'] > rd.uniform(0, sum(total)):
            return '{}nb'.format(value if value != 'W' else 0)
        elif extras['wd']['total'] > rd.uniform(0, sum(total)):
            return '{}wd'.format(rvg(extras['wd']) - 1)
        elif not value and extras['lb']['total'] > rd.uniform(0, total[0]):
            return '{}lb'.format(rvg(extras['lb']))
        elif not value and extras['b']['total'] > rd.uniform(0, total[0]):
            return '{}b'.format(rvg(extras['b']))
        elif value in (0, 1) and self.loaded_freqs[self.index]['run_outs'].get(value, 1) > rd.uniform(0, total[value]):
            return '{}+W'.format(value)
        else:
            return value

    def _next_striker(self, striker, default):
        ball = self[-1][-1]

        if default is None:
            if 'W' in str(ball):
                ball._next_striker = 1 if ball == 'W' else rd.randint(0, 1)
            else:
                ball._next_striker = (striker + int(str(ball)[0])) % 2

            if abs(self[-1]) == 6:
                ball._next_striker = 1 - ball._next_striker
        else:
            ball._next_striker = default._next_striker

    def _get_dismissal(self, bowler, pship, match_idx, at_crease, striker, default):
        ball = self[-1][-1]
        if default is None:
            if ball == 'W':
                out = at_crease[striker]
                mode = rvg(self.loaded_freqs[self.index]['dismissals'][bowler.style[-1]])
                if mode == 'caught':
                    only_fielders = self.fielders.copy()
                    only_fielders.remove(bowler)
                    fielder = only_fielders[rvg(self.loaded_freqs[self.index]['catches'])]
                elif mode in ('caught behind', 'stumped'):
                    fielder = self.keeper
                else:
                    fielder = None
            else:
                out = rd.choice(at_crease)
                mode = 'run out'
                fielder = rd.choice(self.fielders)
        else:
            out = at_crease[striker if default.batter.out else 1 - striker]
            mode = default._mode
            fielder = getattr(default, '_fielder', None)

        ball._mode = mode
        if fielder is not None:
            ball._fielder = fielder

        fielders = [fielder] if fielder is not None else []
        out.dismissal = super().get_dismissal(mode, bowler, fielders, match_idx)

    def __abs__(self):
        return len(self) if abs(self[-1, 6]) == 6 or self._end() else len(self) - 1


class Over(list):
    def __init__(self, bowler, inn):
        self.index = len(inn)
        self._score = '{} - {}'.format(*inn.score)

        if len(inn) < 2 or bowler != inn[-2].bowlers[-1]:
            bowler.spells.append(np.zeros(4))

        self.bowlers = [deepcopy(bowler)]

    @property
    def score(self):
        return self[-1].score if self else self._score

    def __repr__(self):
        return type(self).__name__ + '({}): {}, {} ov'.format(self, self.score, self.index + 1)

    def __str__(self):
        return ' '.join(map(str, self))

    def __abs__(self):
        return sum(1 for ball in self if str(ball)[1:] not in ('nb', 'wd'))


class Ball:
    def __init__(self, value, at_crease, striker, pship, inn):
        self.value = value
        self.index = inn[-1].index + (abs(inn[-1]) + 1) / 10

        inn.score += [abs(self), 'W' in str(self)]
        self.score = '{} - {}'.format(*inn.score)

        pship[striker] += [int(self), 'wd' not in str(self)]
        pship[2] += [abs(self), 'wd' not in str(self)]
        self.pship = '{4}{8} ({5}) ({6} {0} ({1}), {7} {2} ({3}))'.format(*pship.flatten(), *at_crease,
                                                                          '' if 'W' in str(self) else '*')

    def __repr__(self):
        return type(self).__name__ + '({}): {}, {} ov'.format(self, self.score, self.index)

    def __str__(self):
        return str(self.value)

    def __abs__(self):
        if isinstance(self.value, int):
            return self.value
        elif self == 'W':
            return 0
        else:
            return int(self.value[0]) + (self.value[1:] in ('nb', 'wd'))

    def __int__(self):
        if isinstance(self.value, int) or '+' in self.value:
            return abs(self)
        elif 'nb' in self.value:
            return abs(self) - 1
        else:
            return 0

    def __eq__(self, other):
        return self.value == other
