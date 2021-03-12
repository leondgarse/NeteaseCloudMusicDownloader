#!/usr/bin/env python3

import os
import sys
import argparse
import json
import requests
import netease_rename
import other_downloader
import encrypt
from concurrent.futures import ThreadPoolExecutor


def get_url_2_local_file(url, dist_name):
    if os.path.exists(dist_name):
        print("File %s exists, skip downloading" % (dist_name))
        return dist_name
    dist_path = os.path.dirname(dist_name)
    if not os.path.isdir(dist_path):
        os.makedirs(dist_path, exist_ok=True)

    download_contents = requests.get(url, headers=netease_rename.headers)
    if not download_contents.ok or download_contents.url.endswith("/404"):
        print(">>>> %d is returned in download, dist_name = %s" % (download_contents.status_code, dist_name))
        return None

    if len(download_contents.content) == 524288:
        print(">>>> downloaded size is exactly 512.0KB, it may be an error, dist_name = %s" % (dist_name))
        return None

    with open(dist_name, "wb") as ff:
        write_bytes = ff.write(download_contents.content)
        write_bytes_m = write_bytes / 1024 / 1024
        print("dist_name = %s, bytes write = %.2fM" % (dist_name, write_bytes_m))
    return dist_name


def get_url_content_size(url):
    to_download_size = len(requests.get(url, headers=netease_rename.headers).content)
    print("To download size = %.2fM" % (to_download_size / 1024 / 1024))
    return to_download_size


def netease_download_single_bit_rate(song_id, dist_path=None, SIZE_ONLY=False):
    if not isinstance(song_id, dict):
        song_info = song_id
    else:
        song_info = song_id
        song_id = song_info["id"]

    song_download_url = "http://music.163.com/weapi/song/enhance/player/url?csrf_token="
    params = {"ids": [song_id], "br": 320000, "csrf_token": ""}

    data = encrypt.encrypted_request(params)
    resp = requests.post(song_download_url, data=data, timeout=30, headers=netease_rename.headers)
    resp_json = resp.json()
    if resp_json["code"] == -460:
        print(">>>> Return with cheating in netease_download_single_bit_rate, maybe it is expired time limit, try again later")
        exit(1)

    download_url = resp_json["data"][0]["url"]
    song_format = resp_json["data"][0].get("type", "mp3")
    if download_url == None:
        print(">>>> download_url is None, maybe it is limited by copyright. song_id = %s" % (song_id))
        return None

    if SIZE_ONLY == True:
        return get_url_content_size(download_url)

    temp_download_path = os.path.join(dist_path, "{}-bite_rate-random_num.{}".format(song_id, song_format))
    dist_name = get_url_2_local_file(download_url, temp_download_path)
    if dist_name and song_format == "mp3":
        dist_name = netease_rename.netease_cache_rename_single(
            song_info, temp_download_path, dist_path, KEEP_SOURCE=False, song_format=song_format
        )
        return dist_name


# https://github.com/Binaryify/NeteaseCloudMusicApi/blob/master/module/song_url.js
def netease_download_single_outer(song_id, dist_path=None, SIZE_ONLY=False):
    if not isinstance(song_id, dict):
        song_info = song_id
    else:
        song_info = song_id
        song_id = song_info["id"]

    url_base = "http://music.163.com/song/media/outer/url?id={}.mp3"
    url = url_base.format(song_id)

    if SIZE_ONLY == True:
        return get_url_content_size(url)

    temp_download_path = os.path.join(dist_path, "{}-bite_rate-random_num.{}".format(song_id, "mp3"))
    dist_name = get_url_2_local_file(url, temp_download_path)
    if dist_name:
        dist_name = netease_rename.netease_cache_rename_single(
            song_info, temp_download_path, dist_path, KEEP_SOURCE=False, song_format="mp3"
        )
        return dist_name


def downloader_wrapper(single_download_func, song_id, dist_path):
    song_info, _ = netease_rename.detect_netease_music_name(song_id)
    song_artist_ne = song_info["artist"]
    song_name_ne = song_info["title"]
    print(">>>> song_id = %s, song_name_ne = %s, song_artist_ne = %s" % (song_id, song_name_ne, song_artist_ne))
    dist_name = netease_rename.generate_target_file_name(dist_path, song_name_ne, song_artist_ne, "mp3")
    if os.path.exists(dist_name):
        print("File %s exists, skip downloading, song_id = %s" % (dist_name, song_id))
        return dist_name

    keyword = " ".join([song_artist_ne, song_name_ne])
    download_url, song_name, song_artist, song_format = single_download_func(keyword)
    if download_url == None:
        return None

    dist_name = netease_rename.generate_target_file_name(dist_path, song_name, song_artist, song_format)
    dist_name = get_url_2_local_file(download_url, dist_name)
    return dist_name


def netease_download_list(song_list, dist_path, single_download_func=netease_download_single_bit_rate):
    song_list = list(song_list)
    download_func = lambda song_id: single_download_func(song_id, dist_path)

    executor = ThreadPoolExecutor(max_workers=args.num_workers)
    rets = executor.map(download_func, song_list)

    song_not_downloaded = []
    song_downloaded = []
    for ii, song_id in zip(rets, song_list):
        if ii == None:
            song_not_downloaded.append(song_id)
        else:
            song_downloaded.append(song_id)

    print("")
    print("Song not downloaded:")
    for ss in netease_rename.detect_netease_music_name_list(song_not_downloaded):
        print("    %s: %s - %s" % (ss["song_id"], ss["artist"], ss["title"]))
    print("")
    print("Song downloaded id: %s\n" % (song_downloaded))
    print("Song not downloaded id: %s\n" % (song_not_downloaded))
    print("Downloaded = %d, NOT downloaded = %d\n" % (len(song_downloaded), len(song_not_downloaded)))

    return {"song_downloaded": song_downloaded, "song_not_downloaded": song_not_downloaded}


def parse_arguments(argv):
    default_dist_path = "./netease_download_music"
    default_playlist_id = "101562485"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Download Netease song by <playlist> ID\n"
            "Also support specify a <song_id_list> or <album_id>to download\n"
            "Also support download Baidu, QQ, Migu, Kugou source\n"
            "\n"
            "default dist path: %s\n"
            "default playlist id: %s" % (default_dist_path, default_playlist_id)
        ),
    )
    parser.add_argument("-n", "--num_workers", type=int, help="Thread number for downloading", default=10)
    parser.add_argument("-d", "--dist_path", type=str, help="Download output path", default=default_dist_path)
    parser.add_argument("-p", "--playlist", type=str, help="Playlist id to download", default=default_playlist_id)
    parser.add_argument("-a", "--album", type=str, help="Album id used to download", default=None)
    parser.add_argument("-Q", "--queue", action="store_true", help="Download song in cached queue file")
    parser.add_argument(
        "-S", "--song_id_list", nargs="*", type=str, help="Specify song id list to download. Format 1 2 3 or 1, 2, 3"
    )

    parser.add_argument("--outer", action="store_true", help="Download from netease default output url, DEFAULT one")
    parser.add_argument("--bitrate", action="store_true", help="Download with bitrate=320k from netease")
    parser.add_argument("--baidu_flac", action="store_true", help="Download with flac format from Baidu")
    parser.add_argument("--baidu_mp3", action="store_true", help="Download with mp3 format from Baidu")
    parser.add_argument("--qq", action="store_true", help="Download from QQ music")
    parser.add_argument("--migu", action="store_true", help="Download from Migu music")
    parser.add_argument("--kugou", action="store_true", help="Download from Kugou music")
    parser.add_argument("--all", action="store_true", help="Download with all downloaders")

    args = parser.parse_args(argv)
    if args.song_id_list == None or len(args.song_id_list) == 0:
        if args.album != None:
            args.song_id_list = netease_rename.netease_parse_album_2_list(args.album)
        elif args.queue:
            args.song_id_list = netease_rename.netease_cached_queue_2_list()
        else:
            args.song_id_list = netease_rename.netease_parse_playlist_2_list(args.playlist)
    else:
        args.song_id_list = [int(ss.replace(",", "")) for ss in args.song_id_list]

    if args.all:
        args.bitrate = True
        args.qq = True
        args.migu = True
        args.kugou = True
        args.baidu_mp3 = True
        args.baidu_flac = True
        args.outer = True

    args.single_download_funcs = []
    if args.bitrate == True:
        args.single_download_funcs.append(netease_download_single_bit_rate)

    if args.qq == True:
        args.single_download_funcs.append(other_downloader.qq_download_single)
    if args.migu == True:
        args.single_download_funcs.append(other_downloader.migu_download_single)
    if args.kugou == True:
        args.single_download_funcs.append(other_downloader.kugou_download_single)
    if args.baidu_mp3 == True:
        args.single_download_funcs.append(other_downloader.baidu_download_single_mp3)
    if args.baidu_flac == True:
        args.single_download_funcs.append(other_downloader.baidu_download_single_flac)

    # All the lambda func will be the last appended one [ ??? ]
    # for func in single_download_funcs:
    #     func_w = lambda song_id, dist_path: downloader_wrapper(func, song_id, dist_path)
    #     func_w.__name__ = func.__name__
    #     args.single_download_funcs.append(func_w)

    if len(args.single_download_funcs) == 0 or args.outer == True:
        args.single_download_funcs.append(netease_download_single_outer)

    return args


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    for single_download_func in args.single_download_funcs:
        print(">>>> Downlader: %s" % single_download_func.__name__)
        if "netease_" in single_download_func.__name__:
            func = single_download_func
        else:
            func = lambda song_id, dist_path: downloader_wrapper(single_download_func, song_id, dist_path)
        netease_download_list(args.song_id_list, args.dist_path, single_download_func=func)
