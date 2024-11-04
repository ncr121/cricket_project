"""
This module contains functions to download ball-by-ball data and player names
and identifiers from cricsheet.org.

It also contains functions to load this data from downloaded files, filter
matches based on start date and teams, and finally to retrieve player
atrributes from cricinfo.
"""

import json
import os
import requests
import shelve
import pandas as pd
from bs4 import BeautifulSoup
from datetime import date
from zipfile import ZipFile

people = pd.read_csv('people.csv', index_col=0, usecols=['identifier','key_cricinfo']).squeeze('columns')
names = pd.read_csv('names.csv', index_col=0).squeeze('columns')


def download(url, file):
    """
    Download a file, for example .csv, .zip etc, from a specified url.

    Parameters
    ----------
    url : str
        url to download file from.
    file : str
        filename to save as.

    Returns
    -------
    None.

    """
    with open(file, 'wb') as f:
        f.write(requests.get(url).content)


def download_data():
    """
    Download most recent versions of test match and individual data stored from
    cricsheet.org.

    Returns
    -------
    None.

    """
    for csv_name in ('people.csv', 'names.csv'):
        download('https://cricsheet.org/register/' + csv_name, csv_name)

    download('https://cricsheet.org/downloads/tests_male_json.zip', 'temp.zip')

    with ZipFile('temp.zip', 'r') as z:
        fnames = z.namelist()
        z.extract(fnames.pop(fnames.index('README.txt')))
        z.extractall('tests_json', fnames)


def get_filenames(all_teams=None, start_date=None, end_date=None):
    """
    Select matches only if they fall in a specified timeframe or if they are
    played between two whitelisted teams.

    Parameters
    ----------
    all_teams : list, optional
        List of whitelisted teams. The default is None.
    start_date : str, optional
        Lower bound for start of a match. The default is None.
    end_date : str, optional
        Upper bound for start of a match. The default is None.

    Yields
    ------
    str
        filename of match.

    """
    if start_date is None:
        start_date = '2000-01-01'

    if end_date is None:
        end_date = str(date.today())

    if all_teams == 'main':
        all_teams = {'Australia', 'Bangladesh', 'England', 'India', 'New Zealand', 'Pakistan', 'Sri Lanka',
                     'South Africa', 'West Indies'}

    for line in reversed(open('README.txt').readlines()):
        try:
            mat_date, *_, mat_idx, teams_str = line.split(' - ')
            teams = teams_str.replace('\n', '').split(' vs ')
            if start_date <= mat_date <= end_date and (all_teams is None or set(teams).issubset(all_teams)):
                yield mat_idx + '.json'
        except ValueError:
            break


def load_match(fname):
    """
    Load match data from a .json file.

    Parameters
    ----------
    fname : str
        filename of match.

    Returns
    -------
    dict
        dictionary format of .json file.

    """
    return json.load(open(os.path.join(os.getcwd(), 'tests_json', fname)))


def get_new_player_info(identifier):
    """
    Load new player information from cricinfo, if `identifier` has not been
    seen before.

    Parameters
    ----------
    identifier : str
        unique identifer of player.

    Returns
    -------
    dict
        attributes of players's role and style.

    """
    full_name = names[names.index == identifier][0]
    key = int(people[people.index == identifier][0])
    url = 'https://www.espncricinfo.com/player/' + full_name.replace(' ', '-') + '-' + str(key)
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
    root = (soup.body.div.section.section.find('div', class_='ds-relative', recursive=False).div
            .find('div', class_='ds-flex ds-space-x-5').find('div', class_='ds-grow', recursive=False)
            .find('div', class_='ds-p-4').div.div)

    return dict((t.text for t in tag.contents) for tag in root.contents)


def get_player_info(name, identifier):
    """
    Load player information from stored shelved if `identifier` has been seen
    before, else retreive this information from cricinfo.

    Parameters
    ----------
    name : str
        player name.
    identifier : str
        unique identifer of player.

    Returns
    -------
    dict
        attribute of player's role and style.

    """
    db = shelve.open('cricinfo')
    if identifier not in db:
        print('New Player:', name)
        db[identifier] = get_new_player_info(identifier)

    return db[identifier]


if __name__ == '__main__':
    download_data()
