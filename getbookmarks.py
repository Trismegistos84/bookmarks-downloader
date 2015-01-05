#!/usr/bin/python
''' This script requires youtube-dl and ffmpeg '''

import sqlite3
import collections
import sys
import subprocess
import os
import traceback


bookmarks_path = '/home/wolk/.mozilla/firefox/s3p97vew.default/places.sqlite'
music_path = ['Bookmarks Toolbar', 'tmp', 'music']

SongTag = collections.namedtuple('SongTag', 'title artist genre comment')
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


def create_dir(base, genre):
    path = os.path.join(base, genre)
    if not os.path.exists(path):
        os.mkdir(path)

    return path

def songname_to_filename(songname):
    return songname.replace('/', '_') + '.m4a'


def clean_songname(title):
    title = title.replace(' - YouTube', '')
    title = title.replace(u'\u2014', '-') # \u2014 is long dash
    title = title.replace(u'\u25b6', '') # remove play triangle
    return title.strip()


def download_song(url, output_path):
    cmd = ['youtube-dl', '-f', 'bestaudio', '-o', output_path, url]
    subprocess.check_output(cmd, stderr=subprocess.STDOUT)


def tag_song(filename, tags, output_dir):
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


def guess_tags(songname, genre):
    idx = songname.find('-')
    title = ''
    artist = ''
    if idx != -1:
        title = songname[:idx].strip()
        artist = songname[idx + 1:].strip()

    return SongTag(title, artist, genre, 'youtube')


def acquire_song(song, genre, output_dir):
    songname = clean_songname(song.title)
    filename = songname_to_filename(songname)
    download_song(song.url, filename)
    tags = guess_tags(songname, genre)
    tag_song(filename, tags, output_dir)

def print_error_info(info):
    print "# Genre: " + info[0]
    print "# Title: " + info[1]
    print "# Traceback: \n" + info[2]
    if info[3] != None:
        print "# Application output:\n" + info[3]
    print


def main():
    out_folder = sys.argv[1]
    bookmarks = MozillaBookmarks(bookmarks_path)
    music_folder_id = bookmarks.get_folder_id(music_path)
    genres = bookmarks.get_folders(music_folder_id)
    failed_elements = []
    for genre in genres:
        genre_dir = create_dir(out_folder, genre.title)
        songs = bookmarks.get_bookmarks(genre.id)
        failed = False
        for song in songs:
            print "Fetching song " + genre.title + "/" + song.title + " ...",
            sys.stdout.flush()
            try:
                acquire_song(song, genre.title, genre_dir)
                print "done"
            except subprocess.CalledProcessError as exc:
                print "error"
                failed_elements.append((genre.title, song.title, traceback.format_exc(), exc.output))
            except Exception as exc:
                print "error"
                failed_elements.append((genre.title, song.title, traceback.format_exc(), None))

    if len(failed_elements) > 0:
        print "\n=== Failed elements ==="
        for fe in failed_elements:
            print_error_info(fe)

main()
