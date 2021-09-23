#!/usr/bin/env python3

import requests
import json
import io
import os
import sys
import argparse
import eyed3
import shutil
from datetime import datetime
from time import sleep
from PIL import Image
import pickle

headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"}


class Requsets_with_login:
    def __init__(self, user_data_bak_path=None):
        if user_data_bak_path == None:
            save_name = os.path.splitext(os.path.basename(__file__))[0] + "_cookie.pkl"
            save_dir = os.path.dirname(os.path.abspath(__file__))
            self.user_data_bak_path = os.path.join(save_dir, save_name)
        else:
            self.user_data_bak_path = user_data_bak_path

        if os.path.exists(self.user_data_bak_path):
            self.__reload_cookie__()
        else:
            self.__new_login__()

    def __new_login__(self):
        print(">>>> Requires login first")
        user_name = input("Netease user_name: ")
        password = input("Netease password: ")
        print(">>>> [Login info] user_name: {}, password: {}".format(user_name, password))
        self.__request_login__(user_name, password)

    def __request_login__(self, user_name, password):
        from encrypt import encrypted_request
        from hashlib import md5

        session = requests.Session()
        session.cookies.set("os", "pc", domain="music.163.com")
        password_md5 = md5(password.encode("utf-8")).hexdigest()

        if user_name.isdigit() and len(user_name) == 11:  # phone number
            login_url = "http://music.163.com/weapi/login/cellphone"
            params = dict(
                phone=user_name,
                password=password_md5,
                countrycode="86",
                rememberLogin="true",
            )
        else:
            login_url = "http://music.163.com/weapi/login"
            params = dict(
                phone=user_name,
                password=password_md5,
                rememberLogin="true",
            )
        params = encrypted_request(params)

        ret = session.post(login_url, data=params, headers=headers)
        assert ret.ok and ret.json()["code"] == 200

        print(">>>> Save user data to:", self.user_data_bak_path)
        with open(self.user_data_bak_path, "wb") as ff:
            pickle.dump({"user_name": user_name, "password": password, "cookies": session.cookies}, ff)

        self.session = session

    def __reload_cookie__(self):
        # print(">>>> Load user data from:", self.user_data_bak_path)
        with open(self.user_data_bak_path, "rb") as ff:
            user_data = pickle.load(ff)
        cookies = user_data["cookies"]
        if sum([ii.is_expired() for ii in cookies]) != 0:  # expired
            print(">>>> user login data expired, login again:", {ii.name: ii.is_expired() for ii in cookies})
            self.__request_login__(user_data["user_name"], user_data["password"])
        else:
            self.session = requests.Session()
            self.session.cookies.update(cookies)

    def get(self, url):
        return self.session.get(url, headers=headers)

    def post(self, url, data=None, timeout=30):
        return self.session.post(url, data=data, timeout=timeout, headers=headers)


def detect_netease_music_name(song_id):
    # return song_id, None
    # url_base = "http://music.163.com/api/song/detail/?id={}&ids=[{}]"
    # url_target = url_base.format(song_id, song_id)
    url_base = 'http://music.163.com/api/v3/song/detail?id=%s&c=[{"id":"%s"}]'
    url_target = url_base % (song_id, song_id)

    resp = requests.get(url_target, headers=headers)
    retry_count = 10
    while resp.status_code != 200 and retry_count > 0:
        print(">>>> resp status_code is NOT 200, here song_id = %s, retry count = %d" % (song_id, retry_count))
        sleep(1)
        resp = requests.get(url_target, headers=headers)
        retry_count -= 1

    rr = resp.json()
    if rr["code"] == -460:
        print(">>>> Return with cheating in detect_netease_music_name, maybe it is expired time limit, try again later")
        exit(1)
    if len(rr.get("songs", "")) == 0:
        print(">>>> returned 200 OK, but song info is empty, remove it and try again, song_id = %s" % (song_id))
        exit(1)

    # print(">>>> song_id:", song_id)
    if rr["songs"][0]["name"] is None:
        # print(">>>> Private cloud disk one.")
        song_info = {"id": song_id, "title": str(song_id), "artist": "none"}
        return song_info, rr

    song_info = {}
    song_info["title"] = rr["songs"][0]["name"].replace("\xa0", " ")
    song_info["artist"] = ",".join([ii["name"] for ii in rr["songs"][0]["ar"]])
    song_info["album"] = rr["songs"][0]["al"]["name"]
    song_info["track_num"] = (int(rr["songs"][0]["no"]), int(rr["songs"][0]["cd"]))
    song_info["cover_image"] = rr["songs"][0]["al"]["picUrl"]
    song_info["id"] = song_id

    album_detail = netease_get_album_detial(rr["songs"][0]["al"]["id"])
    publish_time = int(rr["songs"][0]["publishTime"])
    if publish_time == 0:
        publish_time = int(album_detail["album"]["publishTime"])
    song_info["year"] = str(datetime.fromtimestamp(publish_time / 1000).year)
    song_info["album_artist"] = album_detail["album"]["artist"]["name"]

    return song_info, rr


def detect_netease_music_name_list(song_list):
    for song_id in song_list:
        ss, rr = detect_netease_music_name(song_id)
        ss.update({"song_id": song_id})
        yield ss


def netease_parse_playlist_2_list(playlist_id):
    # url_playlist_base = "http://music.163.com/api/playlist/detail?id={}"
    # url_playlist_base = "http://localhost:3000/playlist/detail?id={}"
    url_playlist_base = "https://music.163.com/api/v6/playlist/detail?id={}"
    url_playlist = url_playlist_base.format(playlist_id)

    ret = Requsets_with_login().post(url_playlist)
    assert ret.ok and ret.json()["code"] == 200

    play_list = ret.json()["playlist"]["trackIds"]
    for song_item in play_list:
        yield song_item["id"]


def netease_get_album_detial(album_id):
    url_album_base = "http://music.163.com/api/album/{}"
    # url_album_base = "https://music.163.com/weapi/vipmall/albumproduct/detail?id={}"
    url_album = url_album_base.format(album_id)
    # resp = requests.get(url_album, headers=headers)
    resp = Requsets_with_login().post(url_album)
    return resp.json()


def netease_parse_album_2_list(album_id):
    album_detail = netease_get_album_detial(album_id)
    for song_item in album_detail["album"]["songs"]:
        yield song_item["id"]


def netease_cached_queue_2_list():
    cached_queue = os.path.expanduser("~/.cache/netease-cloud-music/StorageCache/webdata/file/queue")
    with open(cached_queue, "r") as ff:
        rr = json.load(ff)
    for song_item in rr:
        yield song_item["track"]["id"]


def netease_cached_queue_2_song_info():
    from datetime import datetime

    cached_queue = os.path.expanduser("~/.cache/netease-cloud-music/StorageCache/webdata/file/queue")
    url_album_base = "http://music.163.com/api/album/{}"

    with open(cached_queue, "r") as ff:
        rr = json.load(ff)
    for song_item in rr:
        if song_item["track"]["name"] is None:  # Private cloud disk one
            yield {"id": song_id, "title": str(song_id), "artist": "cloud_disk"}
        else:
            song_info = {}
            song_info["title"] = song_item["track"]["name"].replace("\xa0", " ")
            song_info["artist"] = ",".join([ii["name"] for ii in song_item["track"]["artists"]])
            song_info["album"] = song_item["track"]["album"]["name"]
            song_info["track_num"] = (int(song_item["track"]["position"]), int(song_item["track"]["cd"]))
            song_info["id"] = song_item["track"]["id"]
            song_info["cover_image"] = song_item["track"]["album"]["picUrl"]
            song_info["url"] = song_item.get("lastPlayInfo", {}).get("retJson", {}).get("url", None)

            album_detail = netease_get_album_detial(song_item["track"]["album"]["id"])
            # print(url_album, album_detail["code"])
            song_info["year"] = str(datetime.fromtimestamp(int(album_detail["album"]["publishTime"]) / 1000).year)
            song_info["album_artist"] = album_detail["album"]["artist"]["name"]
            yield song_info


def generate_target_file_name(dist_path, title, artist, song_format="mp3"):
    aa = artist.replace(os.sep, " ").replace(":", " ").replace("?", " ").strip()
    tt = title.replace(os.sep, " ").replace(":", " ").replace("?", " ").strip()
    dist_name = os.path.join(dist_path, "%s - %s" % (aa, tt)) + "." + song_format

    return dist_name


def netease_cache_rename_single(song_info, file_path, dist_path, KEEP_SOURCE=True, song_format="mp3", SAVE_COVER_IAMGE_SIZE=320):
    if not os.path.exists(dist_path):
        os.mkdir(dist_path)

    if isinstance(song_info, dict):
        song_id = song_info["id"]
    else:
        song_id = song_info
        song_info, _ = detect_netease_music_name(song_id)
    try:
        tt = eyed3.load(file_path)
        tt.initTag(eyed3.id3.ID3_V2_3)
        tt.tag.title = song_info["title"]
        tt.tag.artist = song_info["artist"]
        tt.tag.album = song_info.get("album", "none")
        tt.tag.album_artist = song_info.get("album_artist", "none")
        tt.tag.track_num = tuple(song_info.get("track_num", (0, 0)))
        tt.tag.recording_date = eyed3.core.Date.parse(song_info.get("year", "1970"))
        print(
            "song_id = %s, tt.tag {title = %s, artist = %s, album = %s, album_artist = %s, track_num = %s, year = %s}"
            % (song_id, tt.tag.title, tt.tag.artist, tt.tag.album, tt.tag.album_artist, tt.tag.track_num, song_info.get("year", "1970"))
        )

        if SAVE_COVER_IAMGE_SIZE > 0 and "cover_image" in song_info:
            pic_url = song_info["cover_image"]
            resp = requests.get(pic_url)
            image_data = resp.content
            cc = Image.open(io.BytesIO(image_data))
            if cc.mode != "RGB":
                cc = cc.convert("RGB")
            ww, hh = cc.size
            max_size = min([max([ww, hh]), SAVE_COVER_IAMGE_SIZE])
            target_ww = max_size if ww > hh else int(max_size * ww / hh)
            target_hh = max_size if hh > ww else int(max_size * hh / ww)
            dd = cc.resize((target_ww, target_hh))
            buf = io.BytesIO()
            dd.save(buf, format="JPEG")
            tt.tag.images.set(3, buf.getvalue(), "image/jpeg", "album cover")
        tt.tag.save(encoding="utf8")
    except UnicodeDecodeError as err:
        print("EyeD3 decode error: %s" % err)

    dist_name = generate_target_file_name(dist_path, song_info["title"], song_info["artist"], song_format)
    if dist_name != file_path:
        if KEEP_SOURCE == True:
            shutil.copyfile(file_path, dist_name)
        else:
            os.rename(file_path, dist_name)

    return dist_name


def netease_cache_rename(source_path, dist_path, KEEP_SOURCE=True):
    for file_name in os.listdir(source_path):
        if not file_name.endswith(".mp3"):
            continue
        if not len(file_name.split("-")) == 3:
            print(">>>> File %s not in format <song id>-<bite rate>-<random number>.mp3" % (file_name))
            continue

        song_id = file_name.split("-")[0]
        netease_cache_rename_single(song_id, os.path.join(source_path, file_name), dist_path, KEEP_SOURCE)


def parse_arguments(argv):
    HOME_DIR = os.getenv("HOME")
    default_source_path = os.path.join(HOME_DIR, ".cache/netease-cloud-music/CachedSongs")
    default_dist_path = "./output_music"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Rename netease-cloud-music Ubuntu client cached files\n"
            "From: source_path/<song id>-<bite rate>-<random number>.mp3\n"
            "To: dist_path/<artist name> - <song title>.mp3\n"
            "\n"
            "default source path: %s\n"
            "default dist path: %s" % (default_source_path, default_dist_path)
        ),
    )
    parser.add_argument("-d", "--dist_path", type=str, help="Music output path", default=default_dist_path)
    parser.add_argument("-s", "--source_path", type=str, help="Music source path", default=default_source_path)
    parser.add_argument(
        "-r", "--remove_source", action="store_true", help="Remove source files, default using cp instead of mv"
    )
    parser.add_argument(
        "--song_id_list", nargs="*", type=str, help="Specify song id list to detect song name. Format 1 2 3 or 1, 2, 3"
    )

    args = parser.parse_args(argv)
    args.keep_source = not args.remove_source
    return args


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    if args.song_id_list == None or len(args.song_id_list) == 0:
        print("source = %s, dist = %s" % (args.source_path, args.dist_path))
        netease_cache_rename(args.source_path, args.dist_path, args.keep_source)
    else:
        song_id_list = [int(ss.replace(",", "")) for ss in args.song_id_list]
        for ss in detect_netease_music_name_list(song_id_list):
            print("    %s: %s - %s" % (ss["song_id"], ss["artist"], ss["title"]))
