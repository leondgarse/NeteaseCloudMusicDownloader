#!/usr/bin/env python3

import os
import sys
import argparse
import netease_rename
import netease_download_playlist
from concurrent.futures import ThreadPoolExecutor
import json


def netease_refresh_by_songlist_single(song_id, source_path, dist_path, single_download_func, WITH_SIZE_CHECK=False):
    # print(song_id)
    if not isinstance(song_id, dict):
        song_info, _ = netease_rename.detect_netease_music_name(song_id)
    else:
        song_info = song_id
        song_id = song_info["id"]
    source_path_file = netease_rename.generate_target_file_name(
        source_path, song_info["title"], song_info["artist"], song_format="mp3"
    )
    dist_path_file = netease_rename.generate_target_file_name(
        dist_path, song_info["title"], song_info["artist"], song_format="mp3"
    )

    new_downloaded = False
    song_not_found = False
    if os.path.exists(dist_path_file):
        print("Dist file exists: %s, song_id = %s" % (dist_path_file, song_id))
        # temp_file_path = dist_path_file
        return new_downloaded, song_not_found
    elif os.path.exists(source_path_file) and WITH_SIZE_CHECK == False:
        print("Source file exists: %s, song_id = %s" % (source_path_file, song_id))
        temp_file_path = source_path_file
    else:
        temp_file_path = single_download_func(song_info, dist_path)
        new_downloaded = True

        if temp_file_path != None and os.path.exists(source_path_file) and WITH_SIZE_CHECK == True:
            source_size = os.path.getsize(source_path_file)
            downloaded_size = os.path.getsize(temp_file_path)
            print("New download, song_id = %s, title = %s, artist = %s" % (song_id, song_info["title"], song_info["artist"]))
            print("source_size = %.2fM, downloaded_size = %.2fM" % (source_size / 1024 / 1024, downloaded_size / 1024 / 1024))
            if downloaded_size - source_size >= 500000:
                print(">>>> Downloaded size is 500K bigger than source one")
            else:
                new_downloaded = False
                os.remove(temp_file_path)
                temp_file_path = source_path_file
        elif temp_file_path == None and os.path.exists(source_path_file):
            new_downloaded = False
            temp_file_path = source_path_file

    if temp_file_path == None:
        print("Song not found, song_id = %s, title = %s, artist = %s" % (song_id, song_info["title"], song_info["artist"]))
        new_downloaded = False
        song_not_found = True
    else:
        dist_path_file = netease_rename.netease_cache_rename_single(song_info, temp_file_path, dist_path, KEEP_SOURCE=False)
        print("Move %s to %s, song_id = %s" % (temp_file_path, dist_path_file, song_id))

    return new_downloaded, song_not_found


def netease_refresh_by_songlist(source_path, dist_path, song_list, single_download_func, WITH_SIZE_CHECK=False, num_workers=10):
    if not os.path.exists(dist_path):
        os.mkdir(dist_path)

    refresh_func = lambda song_id: netease_refresh_by_songlist_single(
        song_id, source_path, dist_path, single_download_func, WITH_SIZE_CHECK
    )
    executor = ThreadPoolExecutor(max_workers=num_workers)
    rets = executor.map(refresh_func, song_list)

    new_downloaded = []
    song_not_found = []
    for ii, song_id in zip(rets, song_list):
        if ii[0] == True:
            new_downloaded.append(song_id)
        elif ii[1] == True:
            song_not_found.append(song_id)

    print("")
    print("New downloaded size = %d" % (len(new_downloaded)))
    if len(new_downloaded) != 0 and not isinstance(new_downloaded[0], dict):
        new_downloaded = netease_rename.detect_netease_music_name_list(new_downloaded)
    for ss in new_downloaded:
        print("    %s: %s - %s" % (ss["id"], ss["artist"], ss["title"]))
    print()
    print("Song not found, size = %d:" % len(song_not_found))
    if len(song_not_found) != 0 and not isinstance(song_not_found[0], dict):
        song_not_found = netease_rename.detect_netease_music_name_list(song_not_found)
    for ss in song_not_found:
        print("    %s: %s - %s" % (ss["id"], ss["artist"], ss["title"]))
    print()
    song_not_found_ids = [ss["id"] for ss in song_not_found]
    print("Song not found id: %s" % (song_not_found_ids))
    return song_not_found_ids


def parse_arguments(argv):
    default_dist_path = "Netease_refreshed"
    default_playlist_id = "101562485"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Refresh local files in <source_path> by <playlist>, and save to <dist_path>\n"
            "1. Check song list in <playlist>\n"
            "2. If it is in <dist_path>, keep it\n"
            "3. If it is in <source_path>, move it to <dist_path>\n"
            "4. If it is not in local, download it from Netease, then move to <dist_path>\n"
            "All these steps will also update ID3 info and album cover images.\n"
            "Option <--with_size_check> will force checking file size, and keep the bigger one\n"
            "\n"
        ),
    )
    parser.add_argument("source_path", type=str, help="Source folder contains music files")
    parser.add_argument("-n", "--num_workers", type=int, help="Thread number for downloading, default 10", default=10)
    parser.add_argument("-H", "--head", type=int, help="Update only the head [NUM] ones, default -1", default=-1)
    parser.add_argument(
        "-p", "--playlist", type=str, help="Playlist id, default: " + default_playlist_id, default=default_playlist_id
    )
    parser.add_argument("-a", "--album", type=str, help="Album id used to download", default=None)
    parser.add_argument("-Q", "--queue", action="store_true", help="Download song in cached queue file")
    parser.add_argument(
        "-S", "--song_id_list", nargs="*", type=str, help="Specify song id list to download. Format 1 2 3 or 1, 2, 3"
    )
    parser.add_argument(
        "-d", "--dist_path", type=str, help="Dist output path, default: " + default_dist_path, default=default_dist_path
    )
    parser.add_argument("--with_size_check", action="store_true", help="Enable comparing source and downloaded file size")
    parser.add_argument("--outer", action="store_true", help="Download from netease default output url, DEFAULT one")
    parser.add_argument("--bitrate", action="store_true", help="Download with bitrate=320k from netease")

    args = parser.parse_args(argv)
    if args.song_id_list == None or len(args.song_id_list) == 0:
        if args.album != None:
            args.song_id_list = netease_rename.netease_parse_album_2_list(args.album)
        elif args.queue:
            args.song_id_list = netease_rename.netease_cached_queue_2_song_info()
        else:
            args.song_id_list = netease_rename.netease_parse_playlist_2_list(args.playlist)
    else:
        args.song_id_list = [int(ss.replace(",", "")) for ss in args.song_id_list]

    args.song_id_list = list(args.song_id_list)
    if args.head != -1:
        args.song_id_list = args.song_id_list[: args.head]

    if args.bitrate == True:
        args.single_download_func = netease_download_playlist.netease_download_single_bit_rate
    else:
        args.single_download_func = netease_download_playlist.netease_download_single_outer

    return args


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    netease_refresh_by_songlist(
        args.source_path, args.dist_path, args.song_id_list, args.single_download_func, args.with_size_check, args.num_workers
    )
