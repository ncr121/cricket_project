import json
import os
import requests
import shelve
import pandas as pd
from bs4 import BeautifulSoup

names = pd.read_csv('names.csv', index_col=0).squeeze('columns')
people = pd.read_csv('people.csv', index_col=0, usecols=[0,6]).squeeze('columns')


def load_match(fname):
    return json.load(open(os.path.join(os.getcwd(), 'tests_json', fname)))


def get_filenames(start_date=None, end_date=None, all_teams=None):
    if start_date is None:
        start_date = '2000-01-01'

    if end_date is None:
        end_date = '2025-12-31'  # today

    if all_teams is None:
        all_teams = {'Australia', 'Bangladesh', 'England', 'India', 'New Zealand', 'Pakistan', 'Sri Lanka',
                     'South Africa', 'West Indies'}

    for line in reversed(open('README.txt').readlines()):
        try:
            date, *_, match_idx, teams_str = line.split(' - ')
            teams = teams_str.replace('\n', '').split(' vs ')
            if start_date <= date <= end_date and set(teams).issubset(all_teams):
                yield match_idx + '.json'
        except ValueError:
            break


def get_new_player_info(name, identifier):
    try:
        full_name = names[names.index == identifier][0]
    except IndexError:
        full_name = name
    key = int(people[people.index == identifier][0])
    url = 'https://www.espncricinfo.com/player/' + full_name.replace(' ', '-') + '-' + str(key)
    soup = BeautifulSoup(requests.get(url).text, 'html.parser')
    root = (soup.body.div.section.section.find('div', class_='ds-relative', recursive=False).div
            .find('div', class_='ds-flex ds-space-x-5').find('div', class_='ds-grow', recursive=False)
            .find('div', class_='ds-p-4').div.div)

    return dict((t.text for t in tag.contents) for tag in root.contents)


def get_player_info(name, identifier):
    db = shelve.open('cricinfo')
    if identifier not in db:
        print('New Player:', name)
        db[identifier] = get_new_player_info(name, identifier)

    return db[identifier]
