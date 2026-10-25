#!/usr/bin/env python3

import os
import sys
import json
import argparse
import netease_rename


def normalize_name(name):
    return os.path.splitext(os.path.basename(name))[0].lower().replace(" ", "")


def netease_get_song_details(song_ids, batch_size=500):
    song_details = []
    for start in range(0, len(song_ids), batch_size):
        batch = song_ids[start : start + batch_size]
        cc = json.dumps([{"id": int(ii)} for ii in batch])
        url = "https://music.163.com/api/v3/song/detail"
        resp = netease_rename.global_requests_func.post(url, data={"c": cc}).json()
        song_details.extend(resp.get("songs", []))
    return song_details


def build_playlist_name_map(playlist_id):
    """Map normalized "artist - title" file names, as saved by netease_refresh_by_playlist, to song info"""
    song_ids = list(netease_rename.netease_parse_playlist_2_list(playlist_id))
    name_map = {}
    for song in netease_get_song_details(song_ids):
        if song.get("name") is None:
            continue
        artist = ",".join([ii["name"] for ii in song["ar"]])
        song_info = {"id": song["id"], "title": song["name"], "artist": artist}
        file_name = netease_rename.generate_target_file_name("", song["name"], artist)
        name_map[normalize_name(file_name)] = song_info
        name_map.setdefault(normalize_name("{} - {}".format(artist, song["name"])), song_info)
    print(">>>> Playlist {} total songs: {}".format(playlist_id, len(song_ids)))
    return name_map


def netease_get_cloud_songs(limit=500):
    cloud_songs, offset = [], 0
    while True:
        url = "https://music.163.com/weapi/v1/cloud/get"
        resp = netease_rename.global_requests_func.weapi_post(url, {"limit": limit, "offset": offset}).json()
        assert resp["code"] == 200, "Get cloud songs failed: {}".format(resp)
        cloud_songs.extend(resp["data"])
        if not resp.get("hasMore", False) or len(resp["data"]) == 0:
            break
        offset += len(resp["data"])
    print(">>>> Cloud songs total: {}".format(len(cloud_songs)))
    return cloud_songs


def netease_cloud_match_single(cloud_song_id, target_song_id):
    url = "https://music.163.com/weapi/cloud/user/song/match"
    params = {"userId": netease_rename.global_requests_func.user_id, "songId": cloud_song_id, "adjustSongId": target_song_id}
    resp = netease_rename.global_requests_func.weapi_post(url, params).json()
    return resp.get("code") == 200, resp


def netease_cloud_match(playlist_id, dry_run=False):
    name_map = build_playlist_name_map(playlist_id)
    cloud_songs = netease_get_cloud_songs()

    to_match, matched, not_found = [], [], []
    for cloud_song in cloud_songs:
        cloud_song_id = cloud_song["songId"]
        current_id = (cloud_song.get("simpleSong") or {}).get("id")
        candidates = [cloud_song.get("fileName", ""), "{} - {}".format(cloud_song.get("artist", ""), cloud_song.get("songName", ""))]
        target = next((name_map[normalize_name(ii)] for ii in candidates if normalize_name(ii) in name_map), None)
        if target is None:
            not_found.append(cloud_song)
        elif current_id == target["id"]:
            matched.append(cloud_song)
        else:
            to_match.append((cloud_song, target))

    print(">>>> Already matched: {}, to match: {}, not found in playlist: {}".format(len(matched), len(to_match), len(not_found)))
    failed = []
    for cur_id, (cloud_song, target) in enumerate(to_match):
        info = "[{}/{}] {} -> {}: {} - {}".format(
            cur_id + 1, len(to_match), cloud_song.get("fileName"), target["id"], target["artist"], target["title"]
        )
        if dry_run:
            print(">>>> [Dry run]", info)
            continue
        success, resp = netease_cloud_match_single(cloud_song["songId"], target["id"])
        print(">>>>", info, "" if success else "FAILED: {}".format(resp))
        if not success:
            failed.append(cloud_song)

    if len(not_found) > 0:
        print("\n>>>> Cloud songs not found in playlist:")
        for cloud_song in not_found:
            print("    {}: {}".format(cloud_song["songId"], cloud_song.get("fileName")))
    if len(failed) > 0:
        print("\n>>>> Match failed: {}".format([ii.get("fileName") for ii in failed]))


def parse_arguments(argv):
    default_playlist_id = "101562485"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Bind Netease cloud uploaded songs to Netease songs in <playlist>\n"
            "Cloud songs are matched by uploaded file name <artist> - <title>.mp3, or by their ID3 artist / title.\n"
            "Requires login, by scanning QR code or providing MUSIC_U cookie from browser.\n"
        ),
    )
    parser.add_argument(
        "-p", "--playlist", type=str, help="Playlist id, default: " + default_playlist_id, default=default_playlist_id
    )
    parser.add_argument("-D", "--dry_run", action="store_true", help="Only print match results, not actually binding")
    parser.add_argument("--music_u", type=str, default=None, help="Login using MUSIC_U cookie value copied from browser")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    netease_rename.global_requests_func = netease_rename.Requsets_with_login(require_login=True, music_u=args.music_u)
    netease_cloud_match(args.playlist, args.dry_run)
