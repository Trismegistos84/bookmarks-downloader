#!/usr/bin/python
''' This script requires youtube-dl and ffmpeg '''

import sqlite3
import collections
import sys
import subprocess
import os
import traceback
import re


bookmarks_path = '/home/wolk/.mozilla/firefox/s3p97vew.default/places.sqlite'
music_path = ['Bookmarks Toolbar', 'tmp', 'music']

Bookmark = collections.namedtuple('Bookmark', 'title url')
BookmarkFolder = collections.namedtuple('BookmarkFolder', 'id title')


class MozillaBookmarks(object):
    __FOLDER_TYPE = 2
    __BOOKMARK_TYPE = 1
    __ROOT_PARENT_ID = 1

    def __init__(self, path):
        self.__connection = sqlite3.connect(path)
        self.__cursor = self.__connection.cursor()

    def __del__(self):
        self.__connection.close()

    def get_folder_id(self, path):
        query = 'SELECT id from moz_bookmarks where title = ? and parent = ? and type = 2'
        parentid = MozillaBookmarks.__ROOT_PARENT_ID
        for folder in path:
            self.__cursor.execute(query, (folder, parentid))
            parentid = self.__cursor.fetchone()[0]

        return parentid

    def get_folders(self, parentid):
        query = 'SELECT id, title from moz_bookmarks where parent = ? and type = 2'
        self.__cursor.execute(query, (parentid,))
        return [BookmarkFolder(r[0], r[1]) for r in self.__cursor]

    def get_bookmarks(self, parentid):
        query = '''SELECT moz_bookmarks.title, moz_places.url
                   FROM moz_bookmarks JOIN moz_places
                   ON moz_bookmarks.fk = moz_places.id
                   WHERE moz_bookmarks.parent = ?'''
        self.__cursor.execute(query, (parentid,))
        return [Bookmark(c[0], c[1]) for c in self.__cursor]


SongTag = collections.namedtuple('SongTag', 'title artist genre comment')

class SongDownloader:
    def __init__(self):
        pass


    def songname_to_filename(self, songname):
        return songname.replace('/', '_') + '.m4a'


    def bookmark_to_songname(self, title):
        title = title.encode('ascii', 'ignore')
        title = title.replace(' - YouTube', '')
        return title.strip()


    def download_song(self, url, output_path):
        cmd = ['youtube-dl', '-f', 'bestaudio', '-o', output_path, url]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)


    def tag_song(self, filename, tags, output_dir):
        output_path = os.path.join(output_dir, filename)
        if os.path.exists(output_path):
            os.remove(output_path)
        cmd = ['ffmpeg', '-i', filename, '-codec', 'copy',
               '-metadata', 'title=' + tags.title,
               '-metadata', 'artist=' + tags.artist,
               '-metadata', 'genre=' + tags.genre,
               '-metadata', 'comment=' + tags.comment,
               output_path]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        os.remove(filename)


    def guess_tags(self, songname, url, genre):
        idx = songname.find('-')
        title = ''
        artist = ''
        if idx != -1:
            title = songname[:idx].strip()
            artist = songname[idx + 1:].strip()

        servername = get_server_name(url).encode('ascii', 'ignore')
        return SongTag(title, artist, genre, servername)


    def acquire_song(self, song, genre, output_dir):
        songname = self.bookmark_to_songname(song.title)
        filename = self.songname_to_filename(songname)
        self.download_song(song.url, filename)
        tags = self.guess_tags(songname, song.url, genre)
        self.tag_song(filename, tags, output_dir)


    def download(self, song, genre, genre_dir):
        sys.stdout.flush()
        try:
            self.acquire_song(song, genre, genre_dir)
        except subprocess.CalledProcessError as exc:
            return "# Traceback:\n{}\n# Application Output:\n{}".format(traceback.format_exc(), exc.output)
        except Exception as exc:
            return "# Traceback:\n{}".format(traceback.format_exc())

        return None


'''
Get server name from full url.
e.g. 'http://youtube.com/zzz' will parse to 'youtube.com'
'''
def get_server_name(url):
    regex = re.compile('.*?://(.*?)/.*')
    matched = regex.match(url)
    return matched.group(1)


def create_dir(base, genre):
    path = os.path.join(base, genre)
    if not os.path.exists(path):
        os.mkdir(path)

    return path


def print_error_info(info):
    print "# Folder: " + info[0].encode('ascii', 'ignore')
    print "# Bookmark name: " + info[1].encode('ascii', 'ignore')
    print info[2].encode('ascii', 'ignore')
    print


def print_errors(errors):
    if len(errors) > 0:
        print "\n=== Failed elements ==="
        for err in errors:
            print_error_info(err)


def main():
    out_folder = sys.argv[1]
    bookmarks = MozillaBookmarks(bookmarks_path)
    music_folder_id = bookmarks.get_folder_id(music_path)
    genres = bookmarks.get_folders(music_folder_id)
    downloader = SongDownloader()
    errors = []
    for genre in genres:
        genre_dir = create_dir(out_folder, genre.title)
        songs = bookmarks.get_bookmarks(genre.id)
        for song in songs:
            print "Fetching " + genre.title.encode('ascii', 'ignore') + "/" + song.title.encode('ascii', 'ignore') + " ...",
            err = downloader.download(song, genre.title, genre_dir)
            if err is None:
                print "done"
            else:
                print "error"
                errors.append((genre.title, song.title, err))

    print_errors(errors)

main()
