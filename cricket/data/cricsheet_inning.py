"""
This module contains classes that contribute to representing a real inning from
a match. Many of the class methods and atrributes are inherited from classes
fromother modules.
"""


import numpy as np
from copy import deepcopy
from operator import attrgetter, itemgetter

from functions import List
from classes import Batter, InningMethods
from inning import Over, Ball


class RealInning(InningMethods):
    def __init__(self, data, mat):
        """
        Initialise inning from actual data from cricsheet.

        Parameters
        ----------
        data : dict
            innings data.
        mat : RealMatch
            associated match object.

        Returns
        -------
        None.

        """
        batting_idx = mat.teams.index(data['team'])
        super().__init__(mat, batting_idx)
        self.data = data

    def run(self, mat, index=(None,)*2):
        """
        Iterate through innings data to replicate inning statistics.

        Parameters
        ----------
        mat : RealMatch
            match object.
        index : tuple, optional
            Stopping points for overs and balls respectively. The default is (None,)*2.

        Returns
        -------
        None.

        """
        pship = np.zeros((3, 2), int)

        if 'pre' in self.data.get('penalty_runs', {}):
            self.score[0] += self.data['penalty_runs']['pre']

        for over_data in self.data['overs'][:index[0]]:
            self._run_over(over_data, pship, mat)

        if index[1] is not None:
            self._run_over(self.data['overs'][index[0]], pship, mat, index[1])

        for name in self.data.get('absent_hurt', []):
            player = mat.players[self.batting_team][name]
            batter = Batter(player, None, mat.players[self.batting_team].index(player))
            batter.dismissal = 'absent hurt'
            self.batters.append(batter)

        if 'post' in self.data.get('penalty_runs', {}):
            self.score[0] += self.data['penalty_runs']['post']

        if 'declared' in self.data:
            self[-1][-1].score += 'd'

    def _run_over(self, data, pship, mat, index=None):
        """
        Iterate through over data.

        Parameters
        ----------
        data : dict
            over data.
        pship : np.array
            counter to keep track of current partnership.
        mat : RealMatch
            match object.
        index : int, optional
            Number of balls to run. The default is None.

        Returns
        -------
        None.

        """
        bowler = self._get_bowler(data['deliveries'][0]['bowler'], mat)
        self.overs.append(Over(bowler, self))

        for ball_data in data['deliveries'][:index]:
            self._run_ball(ball_data, pship, mat)

    def _run_ball(self, data, pship, mat):
        """
        Update inning ball-by-ball.

        Parameters
        ----------
        data : dict
            ball data.
        pship : np.array
            counter to keep track of current partnership.
        mat : RealMatch
            match object.

        Returns
        -------
        None.

        """
        if 'replacements' in data:
            for replacement_data in data['replacements'].get('role', []):
                if replacement_data['role'] == 'batter':
                    self.batters[replacement_data['out']].dismissal = 'retired hurt'
                    pship[:] = 0

        at_crease = sorted([self._get_batter(data[key], mat) for key in ('batter', 'non_striker')],
                           key=attrgetter('position'))
        striker = at_crease.index(data['batter'])
        bowler = self._get_bowler(data['bowler'], mat)
        if bowler not in self[-1].bowlers:
            bowler.spells.append(np.zeros(4))
            self[-1].bowlers.append(deepcopy(bowler))

        self[-1].append(RealBall(data, at_crease, striker, pship, self))
        super().update(at_crease, striker, bowler, pship, mat)

    def _get_batter(self, name, mat):
        """
        Get `Batter` object for corresponding batter name.

        Parameters
        ----------
        name : str
            batter name.
        mat : RealMatch
            match object.

        Returns
        -------
        Batter
            Batter object.

        """
        try:
            return self.batters[name]
        except ValueError:
            return super().new_batter(mat.players[self.batting_team][name], mat)

    def _get_bowler(self, name, mat):
        """
        Get `Bowler` object for corresponding bowler name.

        Parameters
        ----------
        name : str
            bowler name.
        mat : RealMatch
            match object.

        Returns
        -------
        Bowler
            Bowler object.

        """
        try:
            return self.bowlers[name]
        except ValueError:
            return super().new_bowler(mat.players[self.bowling_team][name], mat)

    def _get_dismissal(self, bowler, pship, match_idx, *_):
        """
        Assign dismissal type from description.

        Parameters
        ----------
        bowler : Bowler
            Bowler object.
        pship : np.array
            counter to keep track of current partnership.
        match_idx : int
            match identifier.

        Returns
        -------
        None.

        """
        ball = self[-1][-1]
        for wicket_data in ball.data['wickets']:
            out, mode = itemgetter('player_out', 'kind')(wicket_data)
            if mode == 'caught' and wicket_data['fielders'][0]['name'] == self.keeper:
                mode = 'caught behind'

            fielders = [List(self.fielders + [self.keeper]).get(*[fielder['name']] * 2)
                        for fielder in wicket_data.get('fielders', [])]
            self.batters[out].dismissal = super().get_dismissal(mode, bowler, fielders, match_idx)


class RealBall(Ball):
    def __init__(self, data, at_crease, striker, pship, inn):
        """
        Initialise atrributes for each ball.

        Parameters
        ----------
        data : dict
            ball data.
        at_crease : list
            current batters.
        striker : int
            index of current batter on strike.
        pship : np.array
            counter to keep track of current partnership.
        inn : RealInning
            associated inning object.

        Returns
        -------
        None.

        """
        self.data = data
        super().__init__(self._get_value(), at_crease, striker, pship, inn)

    def _get_value(self):
        """
        Return the number of runs scored by the batting team for each ball.

        Raises
        ------
        ValueError
            Unseen description type.

        Returns
        -------
        int
            Number of runs for that ball.

        """
        if 'wickets' in self.data:
            if self.data['wickets'][0]['kind'] == 'run out':
                return '{}+W'.format(int(self))
            elif 'retired' in self.data['wickets'][0]['kind']:
                return int(self)
            else:
                return 'W'
        elif 'extras' not in self.data:
            return int(self)
        elif 'noballs' in self.data['extras']:
            return '{}nb'.format(int(self))
        elif 'wides' in self.data['extras']:
            return '{}wd'.format(abs(self) - 1)
        elif 'legbyes' in self.data['extras']:
            return '{}lb'.format(abs(self))
        elif 'byes' in self.data['extras']:
            return '{}b'.format(abs(self))
        elif 'penalty' in self.data['extras']:
            return 0
        else:
            raise ValueError('unseen value: ' + str(self.data))

    def __abs__(self):
        return self.data['runs']['total']

    def __int__(self):
        return self.data['runs']['batter']
