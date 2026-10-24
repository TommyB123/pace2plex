import os
import json
import re
from pathlib import Path
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.video import Show, Episode, Season
from plexapi.base import MediaContainer
from typing import List
from datetime import datetime, date

# plex account and server info
PLEX_LOGIN = ''
PLEX_PASSWORD = ''
PLEX_SERVER_NAME = ''

# global variables for plex data
plex_account: MyPlexAccount = None
plex_server: PlexServer = None
series: Show = None

# other variables
dry_run: bool = False
SERIES_DATA = None


def resolve_metadata_from_episode_list(season: int, episode: int):
    if season == 0:
        season_name = 'Specials'
        episode_index = episode - 1
    else:
        # Check if 'Specials' is at index 0 of seasons list
        if SERIES_DATA['seasons'] and SERIES_DATA['seasons'][0] == 'Specials':
            season_name = SERIES_DATA['seasons'][season]
        else:
            season_name = SERIES_DATA['seasons'][season - 1]

        if isinstance(season_name, list):
            season_name = season_name[0]  # use the og/outdated season names because that's what's in the series.json file

        if SERIES_DATA['name'] == 'One Pace' and season == SERIES_DATA['lrll_season_number']:
            # special exception for LRLL because it currently has an episode 0 due to the edit's age and series transitioning to 16:9 HD at this point
            episode_index = episode
        else:
            episode_index = episode - 1

    season_data = SERIES_DATA.get(season_name)
    if season_data is None:
        return None
    else:
        if episode_index < len(season_data):
            return season_data[episode_index]
        else:
            # skip episode that's > than the current list
            # this shouldn't happen outside of cases where users have added other One Piece edits to the series.
            return None


def resolve_metadata_from_episode(season: int, episode: int):
    for key, value in SERIES_DATA['episodes'].items():
        if value['season'] == season and value['episode'] == episode:
            return key, value

    return None, None


def main():
    while True:
        clear_terminal()
        print("Enter the option you'd like to use below. Enter any other key to cancel.")
        print(f"1. Dry run status: {'yes' if dry_run is True else 'no'}. Dry run means no actual files or Plex metadata wil be modified. Only example output will be shown.")
        print('2. Manage One Pace')
        print('3. Manage Concentrated Bleach')
        print('4. Manage Naruto Resealed')
        print("5. Delete configuration file. Useful if you've entered incorrect information and don't want to modify it by hand.")
        response = input("Option: ")
        clear_terminal()
        match response:
            case '1':
                ask_dry_run()
            case '2':
                pace_menu()
            case '3':
                cb_menu()
            case '4':
                nr_menu()
            case '5':
                delete_config()
            case _:
                break


def pace_menu():
    global SERIES_DATA
    with open('series/one-pace/series.json') as file:
        SERIES_DATA = json.load(file)

    while True:
        clear_terminal()
        print("Enter the option you'd like to use below. Enter any other key to cancel.")
        print("1. Scan for and organize One Pace episodes")
        print("2. Apply One Pace episode metadata to Plex. Please only do this after you've verified that your One Pace episodes are present in your Plex server.")
        print("3. Apply custom posters and backgrounds to the One Pace series and its seasons. This is strongly recommended as they'll be blank otherwise and you'll need to update them manually.")
        print("4. Apply curated thumbnails to all One Pace episodes. Highly recommended since sometimes the thumbnails Plex generates are lackluster.")
        print("5. OPTIONAL: Organize the Onigashima Paced Wano edit alongside One Pace.")
        print("6. OPTIONAL: Apply Onigashima Paced episode metadata to Plex. Please only do this after you've verified that the episodes are present in your Plex server.")
        response = input("Option: ")
        clear_terminal()
        match response:
            case '1':
                organize_files()
            case '2':
                apply_plex_metadata()
            case '3':
                apply_plex_posters()
            case '4':
                apply_episode_thumbnails()
            case '5':
                organize_onigashima_edit()
            case '6':
                apply_onigashima_plex_metadata()
            case _:
                break

    main()


def cb_menu():
    global SERIES_DATA
    with open('series/concentrated-bleach/series.json') as file:
        SERIES_DATA = json.load(file)

    while True:
        clear_terminal()
        print("Enter the option you'd like to use below. Enter any other key to cancel.")
        print("1. Scan for and organize edited Bleach episodes.")
        print("2. Apply edited Bleach episode metadata to Plex. Please only do this after you've verified that your edited episodes are present in your Plex server.")
        print("3. Apply custom thumbnails authored by the creator of Concentrated Bleach. By default, Plex will simply use ones that it automatically generates. Sometimes they're kind of bad.")
        print("4. Apply metadata to the TYBW arc. Only select this if those episodes are present under a Season 5 folder")
        response = input("Option: ")
        clear_terminal()
        match response:
            case '1':
                organize_files()
            case '2':
                apply_plex_metadata()
            case '3':
                apply_episode_thumbnails()
            case '4':
                apply_tybw_metadata()
            case _:
                break

    main()


def nr_menu():
    global SERIES_DATA
    with open('series/naruto-resealed/series.json') as file:
        SERIES_DATA = json.load(file)

    while True:
        clear_terminal()
        print("Enter the option you'd like to use below. Enter any other key to cancel.")
        print("1. Scan for and organize edited Naruto episodes.")
        print("2. Apply edited Naruto episode metadata to Plex. Please only do this after you've verified that your edited episodes are present in your Plex server.")
        response = input("Option: ")
        clear_terminal()
        match response:
            case '1':
                organize_files()
            case '2':
                apply_plex_metadata()
            case _:
                break

    main()


def ask_dry_run():
    global dry_run
    dry_run = not dry_run


def organize_files():
    cwd = os.path.basename(os.getcwd())
    dest_path = '.' if cwd == SERIES_DATA['name'] else SERIES_DATA['name']

    files_moved = 0
    # organize files first
    for path, dirs, files in os.walk('.'):
        if path == SERIES_DATA['name'] or path.find('Season') != -1:  # skip over season and series folders
            continue

        for file in files:
            if not file.endswith(('.mkv', '.mp4')):  # skip over non-video files
                continue

            final_name = file
            if SERIES_DATA['series_match_type'] == 'season_episodes':
                if SERIES_DATA['name'] == 'One Pace' and 'special_episodes' in SERIES_DATA and file in SERIES_DATA['special_episodes']:
                    # special episodes blacklist & renaming for One Pace
                    special_ep_number = SERIES_DATA['special_episodes'][file]
                    final_name = f'S00E{special_ep_number} - {file}'
                    print(f'Renaming special episode from {file} to {final_name}')
                    season_index = -1
                else:
                    season_index = 0
                    for season in SERIES_DATA['seasons']:
                        if season == 'Specials':
                            continue

                        if SERIES_DATA['name'] == 'One Pace':
                            if season == 'Dressrosa' and file.find('Dressrosa') == -1:
                                # special case snippet to rename Dressrosa episodes for One Pace, specifically from its batch torrent.
                                match = re.match(r'\[One Pace] Chapter ([-0-9]*) \[720p](\[.*])', file)
                                if match is not None and file.find('Chapter') != -1:
                                    episode_number = SERIES_DATA['dressrosa_episodes'].get(match.group(1))
                                    final_name = f'[One Pace][{match.group(1)}] Dressrosa {episode_number} [720p]{match.group(2)}.mkv'
                                    print(f'Renaming Dressrosa episode from {file} to {final_name}')

                        if final_name == file:
                            season_name = season if isinstance(season, list) is False else season[0]
                            match = re.match(SERIES_DATA['series_match_regex'].format(season_name), file)

                        if match is None:
                            season_index += 1
                            continue

                        if SERIES_DATA['name'] == 'One Pace':
                            # another special case to rename cover story special MKVs because their files don't have episode numbers, but the streamable MP4s do
                            if file.endswith('.mkv') and season in ['The Adventures of Buggy\'s Crew', 'The Trials of Koby-Meppo', 'The Adventures of the Straw Hats']:
                                final_name = final_name.replace(season, f'{season} 01')

                        break
                    else:
                        # No regular season matched
                        continue
            elif SERIES_DATA['series_match_type'] == 'absolute_episodes':
                # preemptively remove dub and sub from episode titles for metadata matching since it's present in various edits
                temp_file = file.replace(' (dub)', '')
                temp_file = temp_file.replace(' (sub)', '')

                episode = SERIES_DATA['episodes'].get(temp_file)
                if episode is None:
                    continue

                season_number = episode['season']
                episode_number = episode['episode']
                episode_title = episode['title']
                absolute_episode = episode['absolute_episode']

                abbreviation = SERIES_DATA['abbreviation']
                if SERIES_DATA['name'] == 'Concentrated Bleach' and file.find('Hollowed Bleach') != -1:
                    # abbreviation override for CB's companion edit, Hollowed Bleach
                    abbreviation = 'HB'

                season_index = season_number - 1
                extension = Path(file).suffix
                final_name = f"{SERIES_DATA['name']} S{season_number:02d}E{episode_number:02d} - {episode_title} ({abbreviation} {absolute_episode}){extension}"

            files_moved = move_episode_file(dest_path, path, file, final_name, season_index, files_moved)

    print(f'{files_moved} {"episode" if files_moved == 1 else "episodes"} have been moved to their appropriate folders.')
    print('Please copy these files to your Plex series folder before attempting to apply metadata.\n')
    input('Press enter to continue')


def apply_plex_metadata():
    if plex_auth() is False:
        return

    print(f"Successfully found {SERIES_DATA['name']} series. Searching for episodes to apply metadata to.")
    episodes_changed = 0
    episodes: Episode = series.episodes()
    for episode in episodes:
        if episode.seasonNumber == 0 and 'Specials' not in SERIES_DATA.get('seasons', []):
            # skip specials for edits without specials configured
            continue

        if SERIES_DATA['series_match_type'] == 'season_episodes':
            metadata = resolve_metadata_from_episode_list(episode.seasonNumber, episode.episodeNumber)
        else:
            _, metadata = resolve_metadata_from_episode(episode.seasonNumber, episode.episodeNumber)

        if metadata is None:
            if SERIES_DATA['name'] == 'One Pace' and episode.seasonNumber == SERIES_DATA['wano_season_number'] and episode.episodeNumber > len(SERIES_DATA['Wano']):
                # quietly skip Onigashima Paced Wano episodes
                continue

            if SERIES_DATA['name'] == 'Concentrated Bleach' and episode.seasonNumber == 5:
                # quietly skip episodes from the TYBW arc
                continue

            print(f"Could not find any {SERIES_DATA['name']} metadata for {episode.seasonEpisode.upper()}")
            continue

        changed = apply_metadata_to_episode(episode, metadata)
        if changed is True:
            episodes_changed += 1

    print(f"Applied metadata to {episodes_changed} {SERIES_DATA['name']} episodes.")
    input('Press enter to continue')


def apply_plex_posters():
    if plex_auth() is False:
        return

    asset_path = SERIES_DATA['asset_path']
    poster_path = f"{asset_path}/series_poster.{SERIES_DATA['poster_extension']}"
    if os.path.exists(poster_path) is True:
        series.uploadPoster(filepath=poster_path)
        print(f"Applied series poster to {SERIES_DATA['name']}")

    background_path = f"{asset_path}/background.{SERIES_DATA['background_extension']}"
    if os.path.exists(background_path) is True:
        series.uploadArt(filepath=background_path)
        print(f"Applied background to {SERIES_DATA['name']}")

    for season in series.seasons():
        season_poster_path = f"{SERIES_DATA['asset_path']}/posters/{season.index:02d}.{SERIES_DATA['poster_extension']}"
        if os.path.exists(season_poster_path) is True:
            season.uploadPoster(filepath=season_poster_path)
            print(f'Applied poster to Season {season.index:02d}')

    input('Press enter to continue')


def apply_episode_thumbnails():
    if plex_auth() is False:
        return

    episodes: Episode = series.episodes()
    asset_path = SERIES_DATA['asset_path']
    for episode in episodes:
        if SERIES_DATA['series_match_type'] == 'season_episodes':
            thumbnail_path = f"{asset_path}/thumbnails/{episode.seasonNumber:02d}/{episode.episodeNumber:02d}.{SERIES_DATA['thumbnail_extension']}"
        elif SERIES_DATA['series_match_type'] == 'absolute_episodes':
            original_filename, metadata = resolve_metadata_from_episode(episode.seasonNumber, episode.episodeNumber)
            if metadata is None:
                continue

            thumbnail_folder = 'thumbnails'
            extension = SERIES_DATA['thumbnail_extension']
            if SERIES_DATA['name'] == 'Concentrated Bleach' and original_filename.find('Hollowed Bleach') != -1:
                # override for Hollowed Bleach episodes
                thumbnail_folder = 'hbthumbnails'
                extension = 'jpg'

            thumbnail_path = f"{asset_path}/{thumbnail_folder}/{metadata['absolute_episode']}.{extension}"

        if os.path.exists(thumbnail_path):
            print(f'Applied custom thumbnail to {episode.seasonEpisode.upper()}')
            if dry_run is False:
                episode.uploadPoster(filepath=thumbnail_path)

    input('Press enter to continue.')


def organize_onigashima_edit():
    current_wano_length = len(SERIES_DATA['Wano'])
    print('Since Onigashima Paced is another edit that will be placed alongside One Pace episodes, the episode numbering won\'t line up.')
    print('In order to fix this, we\'ll be renumbering the episode files. Pick an episode number to begin the renumbering at.')
    print('I recommend whatever the latest One Pace Wano episode is and adding 10 to it. This leaves plenty of wiggle room for episode length deviation between edits.')
    print(f'One Pace Wano currently has {current_wano_length} episodes.')
    print('NOTE: The script assumes you aren\'t using Onigashima Paced episodes that have been made obsolete by One Pace proper.')
    while True:
        try:
            new_episode_start = int(input('Choice: '))
        except Exception:
            print('Could not parse your input as an integer.')
            continue

        if new_episode_start < current_wano_length:
            print('You can\t start Onigashima Paced episodes with an episode number less than the current Wano episodes.')
            continue

        break

    cwd = os.path.basename(os.getcwd())
    dest_path = '.' if cwd == SERIES_DATA['name'] else SERIES_DATA['name']

    episodes = []
    for path, dirs, files in os.walk('.'):
        if path == 'One Pace' or path.find('Season') != -1:  # skip over One Pace series and season folders
            continue

        for file in files:
            if file.endswith('.mp4') is False:  # skip over non-mp4 files
                continue

            if file.find('End of Wano') != -1:  # no regex needed for the end of wano episodes at this point
                print(f'{path}/{file}')
                episodes.append((path, file))
                continue

            match = re.match(r'\[[-0-9]*] (?:Onigashima|Onigashima\+) ([0-9]*) - .*.mp4', file)
            if match is not None:
                if int(match.group(1)) >= SERIES_DATA['onigashima_start']:
                    print(f'{path}/{file}')
                    episodes.append((path, file))

    if len(episodes) == 0:
        print('No Wano episodes found')
        input('Press enter to continue')
        return

    print(f'Found {len(episodes)} suitable Onigashima Paced episodes. Now organizing files.')
    episodes.sort()

    # finally organize the files
    for path, name in episodes:
        match = re.match(r'\[[-0-9]*] (?:Onigashima|Onigashima\+|End of Wano) ([0-9]*) - .*.mp4', name)
        original_ep_number = int(match.group(1))
        if name.find('End of Wano') != -1:
            new_episode_number = (SERIES_DATA['onigashima_end'] - SERIES_DATA['onigashima_start'] + original_ep_number) + new_episode_start
        else:
            new_episode_number = (original_ep_number - SERIES_DATA['onigashima_start']) + new_episode_start

        new_name = name.replace(match.group(1), f'{new_episode_number} ({original_ep_number})')
        move_episode_file(dest_path, path, name, new_name, SERIES_DATA['wano_season_number'])

    input('Press enter to continue')


def apply_onigashima_plex_metadata():
    if plex_auth() is False:
        return

    print('Successfully found One Pace series.')

    # try to find the season 35 (Wano)
    print('Attempting to fetch Wano season folder')
    for season in series.seasons():
        if season.index == SERIES_DATA['wano_season_number']:
            wano_season = season
            break

    if wano_season is None:
        print('Could not find the Wano arc. Please ensure it\'s present in your Plex instance under Season 35')
        input('Press enter to continue')
        return

    episodes = wano_season.episodes()
    if len(episodes) <= len(SERIES_DATA['Wano']):
        print('Could not find any episodes beyond One Pace\'s Wano episodes.')
        input('Press enter to continue')
        return

    print('Successfully fetched Wano season folder. Searching for Onigashima Paced episodes to apply metadata to.')
    onigashima_episodes: List[Episode] = []
    for episode in episodes:
        if episode.episodeNumber > len(SERIES_DATA['Wano']):  # assume it's an Onigashima Paced episode
            onigashima_episodes.append(episode)

    episodes_changed = 0
    for i in range(len(onigashima_episodes)):
        episode = onigashima_episodes[i]

        changed = apply_metadata_to_episode(episode, SERIES_DATA['Onigashima'][i])
        if changed is True:
            episodes_changed += 1

    print(f'Applied metadata to {episodes_changed} Onigashima Paced episodes.')
    input('Press enter to continue')


def apply_metadata_to_episode(episode: Episode, metadata: dict):
    changed = False

    # apply episode title
    if episode.title != metadata['title']:
        if dry_run is False:
            episode.editTitle(metadata['title'])
            episode.editSortTitle(metadata['title'])

        changed = True
        print(f"Applied episode title to {episode.seasonEpisode.upper()} ({metadata['title']})")

    # apply episode summary
    new_summary = f"{metadata['summary']}\nManga Chapters: {metadata['chapters']} | Edited Episodes: {metadata['episodes']}"
    if episode.summary != new_summary:
        if dry_run is False:
            episode.editSummary(new_summary)

        changed = True
        print(f"Applied episode summary to {episode.seasonEpisode.upper()}")

    # apply original episode airdate
    date_comp = datetime.combine(date.fromisoformat(metadata['original_airdate']), datetime.min.time())
    if episode.originallyAvailableAt != date_comp:
        if dry_run is False:
            episode.editOriginallyAvailable(metadata['original_airdate'])

        changed = True
        print(f"Applied original release date to {episode.seasonEpisode.upper()} ({metadata['original_airdate']})")

    return changed


def move_episode_file(dest_path: str, source_path: str, file: str, newfile: str, season_index: int, files_moved: int = 0):
    # prepare directories
    if dest_path is None:
        dest_path = SERIES_DATA['name']
        if os.path.exists(SERIES_DATA['name']) is False:
            print(f"creating root series directory for {SERIES_DATA['name']}")
            if dry_run is False:
                os.makedirs(SERIES_DATA['name'])

    season_number = season_index + 1
    season_path = f'Season {season_number:02d}'

    if os.path.exists(f'{dest_path}/{season_path}') is False:
        print(f'creating season folder for season {season_number}')
        if dry_run is False:
            os.makedirs(f'{dest_path}/{season_path}')

    final_file = Path(f'{dest_path}/{season_path}/{newfile}')
    if os.path.exists(final_file):
        # quietly skip over already existing episodes
        return files_moved

    # copy (hardlink) episode to its final destination
    print(f'copying {file} to {season_path}')
    if dry_run is False:
        os.link(f'{source_path}/{file}', final_file)

    files_moved += 1
    return files_moved


def apply_tybw_metadata():
    if plex_auth() is False:
        return

    season: Season = series.seasons()[-1]  # assume the last element in the list is TYBW
    episodes: MediaContainer[Episode] = season.episodes()
    episodes_changed = 0

    for episode in episodes:
        metadata = SERIES_DATA['tybw'][episode.episodeNumber - 1]

        changed = False
        if episode.title != metadata['title']:
            episode.editTitle(metadata['title'])
            episode.editSortTitle(metadata['title'])
            print(f"Applied episode title to {episode.seasonEpisode.upper()} ({metadata['title']})")
            changed = True

        newsummary = f"{metadata['summary']}\nManga Chapters: {metadata['chapters']}"
        if episode.summary != newsummary:
            episode.editSummary(newsummary)
            print(f"Applied episode summary to {episode.seasonEpisode.upper()}")
            changed = True

        if episode.originallyAvailableAt is None or episode.originallyAvailableAt.strftime('%Y-%m-%d') != metadata['original_airdate']:
            episode.editOriginallyAvailable(metadata['original_airdate'])
            print(f'Applied release date to {episode.seasonEpisode.upper()}')
            changed = True

        if changed is True:
            episodes_changed += 1

    print(f'Applied metadata to {episodes_changed} edited Bleach episode(s).')
    input('Press enter to continue.')


def plex_auth():
    check_config()

    global plex_account
    if plex_account is None:
        print('Attempting to authenticate with Plex using your stored credentials.')
        plex_account = MyPlexAccount(PLEX_LOGIN, PLEX_PASSWORD)
        if plex_account is None:
            print('Failed to authenticate with Plex.')
            return False

    global plex_server
    if plex_server is None:
        print(f'Successfully authenticated with Plex. Now attempting to connect to media server ({PLEX_SERVER_NAME})')
        plex_server = plex_account.resource(PLEX_SERVER_NAME).connect()
        if plex_server is None:
            print(f'Failed to connected to the media server ({PLEX_SERVER_NAME})')
            return False

    global series
    if series is None:
        print(f"Searching for {SERIES_DATA['name']} TV series")
        series = plex_server.search(SERIES_DATA['name'], 'show')[0]
        if series is None:
            print(f"Unable to find {SERIES_DATA['name']} TV series. Pleae add it to your plex library and populate it with edited episodes.")
            return False

    return True


def check_config():
    clear_terminal()
    if os.path.exists('config.json') is False:
        # create a new config file
        data = {
            'plex_username': '',
            'plex_password': '',
            'plex_server_name': ''
        }

        print('Writing new config file.')
        with open('config.json', 'x') as file:
            file.write(json.dumps(data))

    with open('config.json') as file:
        plex_data = json.load(file)
        changed = False

        # your plex username or email
        if len(plex_data['plex_username']) == 0:
            plex_data['plex_username'] = input('Enter the email associated with your Plex account\nEmail: ')
            changed = True

        global PLEX_LOGIN
        PLEX_LOGIN = plex_data['plex_username']

        # your plex password
        if len(plex_data['plex_password']) == 0:
            plex_data['plex_password'] = input('Enter the password associated with your Plex account\nPassword: ')
            changed = True

        global PLEX_PASSWORD
        PLEX_PASSWORD = plex_data['plex_password']

        # the name of your plex media server
        if len(plex_data['plex_server_name']) == 0:
            plex_data['plex_server_name'] = input('Enter the name of the media server that contains your desired anime edits.\nServer: ')
            changed = True

        global PLEX_SERVER_NAME
        PLEX_SERVER_NAME = plex_data['plex_server_name']

    if changed is True:
        with open('config.json', 'w') as file:
            file.write(json.dumps(plex_data))

    clear_terminal()


def delete_config():
    if os.path.exists('config.json') is True:
        os.remove('config.json')
        print('Config file has been deleted. You will be prompted to enter your Plex information again next time a Plex API call is made.')
    else:
        print('No configuration file exists.')

    input('Press enter to continue.')

    # reset plex info variables
    global PLEX_LOGIN
    PLEX_LOGIN = ''

    global PLEX_PASSWORD
    PLEX_PASSWORD = ''

    global PLEX_SERVER_NAME
    PLEX_SERVER_NAME = ''


def clear_terminal():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


if __name__ == '__main__':
    main()
