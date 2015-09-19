#!/usr/bin/python
''' This script requires youtube-dl and ffmpeg '''

import sqlite3
import collections
import sys
import subprocess
import os
import traceback
import re
import shutil


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

    '''
    @path -- list representing path e.g ['Bookmarks Toolbar', 'tmp', 'music']
    '''
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

    '''
    @path -- list representing path e.g ['Bookmarks Toolbar', 'tmp', 'music']
    '''
    def walk(self, path):
        rootid = self.get_folder_id(path)
        bookmarks = self.get_bookmarks(rootid)
        folders = self.get_folders(rootid)

        result = [([], folders, bookmarks)]
        folders_to_visit = list(result)

        for folder in folders_to_visit:
            curpath = folder[0]
            for subfolder in folder[1]:
                subfolderpath = list(curpath)
                subfolderpath.append(subfolder.title)

                subfolderfolders = self.get_folders(subfolder.id)

                subfolderbookmarks = self.get_bookmarks(subfolder.id)

                subfolderentry = (subfolderpath, subfolderfolders, subfolderbookmarks)

                result.append(subfolderentry)
                folders_to_visit.append(subfolderentry)

        return result


SongTag = collections.namedtuple('SongTag', 'title artist genre comment')

class SongDownloader:

    def songname_to_filename(self, songname):
        return make_legal_path_component(songname) + '.m4a'

    def clean_bookmark_name(self, title):
        title = title.encode('ascii', 'ignore')
        title = title.replace(' - YouTube', '')
        return title.strip()


    def download_song(self, url, output_path):
        cmd = ['youtube-dl', '-f', 'bestaudio', '-o', output_path, url]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)


    def tag_song(self, filename, tags, outdir):
        output_path = os.path.join(outdir, filename)
        if os.path.exists(output_path):
            os.remove(output_path)
        cmd = ['ffmpeg', '-i', filename, '-codec', 'copy']

        if tags.title is not None :
            cmd = cmd + ['-metadata', 'title=' + tags.title]
        if tags.artist is not None:
            cmd = cmd + ['-metadata', 'artist=' + tags.artist]
        if tags.genre is not None:
            cmd = cmd + ['-metadata', 'genre=' + tags.genre]
        if tags.comment is not None:
            cmd = cmd + ['-metadata', 'comment=' + tags.comment]

        cmd = cmd + [output_path]

        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        os.remove(filename)


    def guess_tags(self, songname, url, bookmarkpath):
        idx = songname.find('-')
        title = None
        artist = None
        if idx != -1:
            title = songname[:idx].strip()
            artist = songname[idx + 1:].strip()

        servername = get_server_name(url).encode('ascii', 'ignore')

        genre = None
        if len(bookmarkpath) > 0:
            genre = bookmarkpath[0]
        return SongTag(title, artist, genre, servername)


    def download(self, song, bookmarkpath, outdir):
        songname = self.clean_bookmark_name(song.title)
        filename = self.songname_to_filename(songname)
        self.download_song(song.url, filename)
        tags = self.guess_tags(songname, song.url, bookmarkpath)
        try:
            self.tag_song(filename, tags, outdir)
        except Exception as excp:
            outfile = os.path.join(outdir, filename)
            shutil.copyfile(filename, outfile)
            raise Exception("Unable to tag song " + songname)



'''
Get server name from full url.
e.g. 'http://youtube.com/zzz' will parse to 'youtube.com'
'''
def get_server_name(url):
    regex = re.compile('.*?://(.*?)/.*')
    matched = regex.match(url)
    return matched.group(1)


def create_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)

def print_error_info(info):
    print("# Folder:", [i.encode('ascii', 'ignore') for i in info[0]])
    print("# Bookmark name: " + info[1].title.encode('ascii', 'ignore'))
    if isinstance(info[2], subprocess.CalledProcessError):
        msg = "# Command: {}\n# Application Output:\n{}".format(info[2].cmd, info[2].output)
        print(msg)
    else:
        print(info[2])
    print("")


def print_errors(errors):
    if len(errors) > 0:
        print("\n=== Failed elements ===")
        for err in errors:
            print_error_info(err)

def make_legal_path_component(path):
    return path.replace('/', '_')

def main():
    out_folder = sys.argv[1]
    bookmarkAccess = MozillaBookmarks(bookmarks_path)
    downloader = SongDownloader()
    errors = []

    for bookmarkpath, folders, bookmarks in bookmarkAccess.walk(music_path):
        fspath = [make_legal_path_component(i) for i in bookmarkpath]
        outdir = os.path.join(out_folder, *fspath)
        create_dir(outdir)
        for bookmark in bookmarks:
            sys.stdout.flush()
            print "Fetching " + bookmark.title.encode('ascii', 'ignore') + " ...",
            try:
                downloader.download(bookmark, bookmarkpath, outdir)
                print("done")
            except Exception as e:
                print("error")
                errors.append((bookmarkpath, bookmark, e))

    print_errors(errors)

main()

