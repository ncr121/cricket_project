"""
This module contains classes that represent real players, teams and matches.
Many of the class methods and atrributes are inherited from classes from
other modules.
"""

from operator import itemgetter

from classes import MatchMethods
from squads import Player, Squad
from loader import load_match, get_player_info
from cricsheet_inning import RealInning

style_map = {'Batting': {'Left hand Bat': 'LH', 'Right hand Bat': 'RH', None: None},
             'Bowling': {'Left arm Fast': 'LAF',
                         'Left arm Fast medium': 'LAF',
                         'Left arm Fast medium, Slow Left arm Orthodox': 'LAMF',
                         'Left arm Medium': 'LAMF',
                         'Left arm Medium fast': 'LAF',
                         'Left arm Slow': 'LAMF',
                         'Left arm Wrist spin': 'LALS',
                         'Legbreak': 'RALS',
                         'Legbreak Googly': 'RALS',
                         'Right arm Bowler': 'RAMF',
                         'Right arm Fast': 'RAF',
                         'Right arm Fast medium': 'RAF',
                         'Right arm Fast medium, Right arm Offbreak': 'RAMF',
                         'Right arm Medium': 'RAMF',
                         'Right arm Medium fast': 'RAF',
                         'Right arm Medium, Legbreak': 'RAMF',
                         'Right arm Medium, Right arm Offbreak': 'RAMF',
                         'Right arm Medium, Right arm Slow medium': 'RAMF',
                         'Right arm Medium fast, Legbreak': 'RAMF',
                         'Right arm Offbreak': 'RAOS',
                         'Right arm Offbreak, Legbreak': 'RAOS',
                         'Right arm Offbreak, Legbreak Googly': 'RAOS',
                         'Right arm Offbreak, Slow Left arm Orthodox': 'RAOS',
                         'Right arm Slow': 'RAMF',
                         'Slow Left arm Orthodox': 'LAOS',
                         None: None}}


class RealPlayer(Player):
    def __init__(self, name, identifier):
        """
        Initiliase player object with identifier from crichseet.org and 
        attributes from cricinfo.

        Parameters
        ----------
        name : str
            player name.
        identifier : str
            unique player identifier.

        Returns
        -------
        None.

        """
        self.info = get_player_info(name, identifier)
        role = self.info.get('Playing Role')
        styles = [style_map[key][self.info.get(key + ' Style')] for key in ('Batting', 'Bowling')]
        super().__init__(name, role, styles)
        self.fielding_style = self.info.get('Fielding Position')


class RealSquad(Squad):
    def __init__(self, team):
        """
        Initialise team.

        Parameters
        ----------
        team : str
            team name.

        Returns
        -------
        None.

        """
        self.team = team
        self.players = {}

    def starting(self, match_info):
        """
        

        Parameters
        ----------
        match_info : dict
            dictionary containing player information for a match.

        Returns
        -------
        tuple
            list of players who played in the match.

        """
        names = match_info['players'][self.team]
        for name in names:
            if name not in self.players:
                self.players[name] = RealPlayer(name, match_info['registry']['people'][name])

        return itemgetter(*names)(self)


class RealMatch(MatchMethods):
    def __init__(self, fname, pdb):
        """
        Initialise match from stored database containing data from
        cricsheet.org.

        Parameters
        ----------
        fname : str
            filename of match.
        pdb : dict
            player database.

        Returns
        -------
        None.

        """
        self.data = load_match(fname)
        info = self.data['info']

        index = int(fname.replace('.json', ''))
        super().__init__(index, info['teams'], pdb, info)
        self.outcome = info['outcome']
        self.player_of_match = info.get('player_of_match')

        print(index, self._get_event(), info['dates'][0])

    def run(self, pdb, index=(None,)*3):
        """
        Run match by feeding the actual data, hence replicating scorecards and
        statistics from the match.

        Parameters
        ----------
        pdb : TYPE
            player database.
        index : tuple, optional
            Stopping points for number of innings, overs and balls
            respectively. The default is (None,)*3.

        Returns
        -------
        None.

        """
        for data in self.data['innings'][:index[0]]:
            self._run_inning(data, self)

        if index[1] is not None:
            self._run_inning(self.data['innings'][index[0]], self, index[1:])

        for team, squad in self.squads.items():
            pdb[team] = squad

    def _run_inning(self, data, mat, index=(None,)*2):
        """
        Run match by feeding the actual data, hence replicating scorecards and
        statistics from the inning. 

        Parameters
        ----------
        data : dict
            innings data.
        index : TYPE, optional
            Stopping points for number of overs and balls respectively.
            The default is (None,)*2.

        Returns
        -------
        None.

        """
        self.innings.append(RealInning(data, mat))
        self[-1].run(self, index)

    def _get_event(self):
        """
        Get the match series and index of the match.

        Returns
        -------
        str
            series and match description.

        """
        try:
            event = self.data['info']['event']
            index = event.get('match_number')
            return '{}, {}{} Test'.format(event['name'], index, ['st', 'nd', 'rd', 'th'][min(3, index - 1)])
        except TypeError:
            return event['name'] + (', ' + event['stage'] if 'stage' in event else '')
        except KeyError:
            return 'unknown event'


if __name__ == '__main__':
    fname = '1249875.json'
    pdb = {team: RealSquad(team) for team in load_match(fname)['info']['teams']}
    m = RealMatch(fname, pdb)
    m.run(pdb)
