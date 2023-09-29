import os
import shelve
import pandas as pd
import random as rd

from functions import rvg
from classes import MatchMethods
from inning import Inning


class Match(MatchMethods):
    def __init__(self, index, teams, pdb):
        super().__init__(index, teams, pdb)
        self.toss = {'decision': rvg(shelve.open(os.getcwd() + '\data\\real_freqs', 'r')['toss']),
                     'winner': rd.choice(self.teams)}

        self.follow_on = False

    @property
    def sessions(self):
        overs = sum(map(abs, self))
        days, overs = divmod(overs, 90)
        sessions, overs = divmod(overs, 30)

        return days, sessions, overs

    @property
    def outcome(self):
        if len(self) == 4:
            if self[3].score[0] >= self.target:
                return {'winner': self[3].batting_team, 'by': {'wickets': 10 - self[3].score[1]}}
            elif self[3].score[1] == 10:
                if self[3].score[0] < self.target:
                    return {'winner': self[3].bowling_team, 'by': {'runs': self.target - self[3].score[0] - 1}}
                else:
                    return {'result': 'tie'}

        if len(self) == 3 and getattr(self, 'target', float('inf')) <= 0:
            return {'winner': self[2].bowling_team, 'by': {'innings': 1, 'runs': 1 - self.target}}

        if self.sessions[0] == 5:
            return {'result': 'draw'}
        else:
            return {'result': 'in progress'}

    @property
    def player_of_match(self):
        return

    def run(self):
        while len(self) < 4:
            try:
                self._next_inning()
            except StopIteration:
                break

    def rewind(self, pdb, index=(None,)*3, run=False):
        new = self.__class__(self.index, self.teams, pdb)
        new.toss = self.toss

        for inn in self[:index[0]]:
            new._next_inning(inn, self, run)

        if index[1] is not None:
            new._next_inning(self[index[0]], self, run, index[1:])

        if run:
            new.run()

        return new

    def _next_inning(self, default=None, old=None, run=False, index=(None,)*2):
        if len(self) >= 2:
            lead = self[0].score[0] - self[1].score[0]
            if len(self) == 2:
                if old is not None:
                    self.follow_on = old.follow_on
                elif lead > 200:
                    self.follow_on = True if lead > 300 or self.sessions[0] >= 3 else bool(rd.randint(0, 1))
            elif len(self) == 3:
                self.target = self[2].score[0] + lead * (-1 if self.follow_on else 1) + 1
                if self.target <= 0:
                    raise StopIteration

        if default is None:
            self.innings.append(Inning(self))
            self[-1].run(self)
        else:
            self.innings.append(default.rewind(index, self, run))


if __name__ == '__main__':
    import squads

    squads_info = pd.read_excel('squads.xlsx', sheet_name=None, index_col='name')
    pdb = {team: squads.Squad(team, info) for team, info in squads_info.items()}
    teams = list(pdb)

    m = Match(0, teams[5:7], pdb)
    m.run()
