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
    with open(file, 'wb') as f:
        f.write(requests.get(url).content)


def download_data():
    for csv_name in ('people.csv', 'names.csv'):
        download('https://cricsheet.org/register/' + csv_name, csv_name)

    download('https://cricsheet.org/downloads/tests_male_json.zip', 'temp.zip')

    with ZipFile('temp.zip', 'r') as z:
        fnames = z.namelist()
        z.extract(fnames.pop(fnames.index('README.txt')))
        z.extractall('tests_json', fnames)


def get_filenames(all_teams=None, start_date=None, end_date=None):
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
    return json.load(open(os.path.join(os.getcwd(), 'tests_json', fname)))


def get_new_player_info(identifier):
    full_name = names[names.index == identifier][0]
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
        db[identifier] = get_new_player_info(identifier)

    return db[identifier]


if __name__ == '__main__':
    download_data()
