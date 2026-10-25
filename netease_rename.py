#!/usr/bin/env python3

import os
import io
import sys
import json
import random
import string
import requests
import argparse
import eyed3
import shutil
from datetime import datetime
from time import sleep
from PIL import Image
import pickle

headers = {
    'Accept': '*/*',
    'Host': 'music.163.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Referer': 'http://music.163.com',
    'Cookie': 'appver=2.0.2; _ntes_nuid={}; NMTID={}'.format(
        ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32)),
        ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32)))
}
global_requests_func = None


class Requsets_with_login:
    """Session with optional login. Login is done by scanning QR code with Netease app, or by providing MUSIC_U cookie.
    Saved cookies are reloaded from user_data_bak_path. If require_login is False and no valid saved cookies, go on without login.
    """
    def __init__(self, user_data_bak_path=None, require_login=False, music_u=None):
        if user_data_bak_path == None:
            save_name = os.path.splitext(os.path.basename(__file__))[0] + "_cookie.pkl"
            save_dir = os.path.dirname(os.path.abspath(__file__))
            self.user_data_bak_path = os.path.join(save_dir, save_name)
        else:
            self.user_data_bak_path = user_data_bak_path

        self.session = self.__default_seesion__()
        self.profile = None
        if music_u is not None:
            self.session.cookies.set("MUSIC_U", music_u, domain=".music.163.com")
            self.profile = self.__check_login__()
            if self.profile is None:
                print(">>>> Provided MUSIC_U is not valid")
            else:
                self.__save_cookie__()
        elif os.path.exists(self.user_data_bak_path):
            self.profile = self.__reload_cookie__()

        if self.profile is None and require_login:
            self.profile = self.__qrcode_login__()
        if self.profile is None:
            if require_login:
                raise RuntimeError("Login failed")
            print(">>>> Go on without login")
        else:
            print(">>>> Logged in as: {}, user_id: {}".format(self.profile["nickname"], self.profile["userId"]))

    def __default_seesion__(self):
        session = requests.Session()
        # Not using headers["Cookie"], or it will override session cookies like MUSIC_U
        session.headers.update({kk: vv for kk, vv in headers.items() if kk != "Cookie"})
        rand_str = lambda: "".join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        default_cookies = {"os": "pc", "appver": "2.9.7", "_ntes_nuid": rand_str(), "NMTID": rand_str()}
        for kk, vv in default_cookies.items():
            session.cookies.set(kk, vv, domain=".music.163.com")
        return session

    @property
    def user_id(self):
        return None if self.profile is None else self.profile["userId"]

    def __check_login__(self):
        try:
            profile = self.weapi_post("https://music.163.com/weapi/w/nuser/account/get").json().get("profile")
        except Exception as err:
            print(">>>> Check login error:", err)
            profile = None
        return profile

    def __music_u_input_login__(self):
        print(">>>> [qrcode] not installed, run `pip install qrcode` to login by scanning QR code in terminal.")
        print("     Or login https://music.163.com in browser, copy value of cookie MUSIC_U from DevTools -> Application -> Cookies")
        music_u = input("MUSIC_U (empty to skip): ").strip()
        if len(music_u) == 0:
            return None
        self.session.cookies.set("MUSIC_U", music_u, domain=".music.163.com")
        profile = self.__check_login__()
        if profile is None:
            print(">>>> Provided MUSIC_U is not valid")
        else:
            self.__save_cookie__()
        return profile

    def __qrcode_login__(self, timeout=180):
        try:
            import qrcode
        except ImportError:
            return self.__music_u_input_login__()

        unikey = self.weapi_post("https://music.163.com/weapi/login/qrcode/unikey", {"type": 1}).json()["unikey"]
        # This url only works when scanned by Netease Cloud Music app, not opened in browser
        qr_url = "https://music.163.com/login?codekey={}".format(unikey)
        print(">>>> Scan QR code using Netease Cloud Music app to login:")
        qr = qrcode.QRCode(border=1)
        qr.add_data(qr_url)
        qr.print_ascii(invert=True)

        prev_code = None
        for _ in range(timeout // 2):
            sleep(2)
            ret = self.weapi_post("https://music.163.com/weapi/login/qrcode/client/login", {"key": unikey, "type": 1}).json()
            code = ret.get("code")
            if code != prev_code:
                print(">>>> QR code login status: {}, {}".format(code, ret.get("message", "")))
                prev_code = code
            if code == 803:  # Success, cookies like MUSIC_U are set by response
                profile = self.__check_login__()
                if profile is not None:
                    self.__save_cookie__()
                return profile
            elif code not in (801, 802):  # 800 expired, 8821 requires verification
                print(">>>> QR code login failed, try providing MUSIC_U cookie from browser instead")
                return None
        print(">>>> QR code login timeout")
        return None

    def __save_cookie__(self):
        print(">>>> Save user cookies to:", self.user_data_bak_path)
        with open(self.user_data_bak_path, "wb") as ff:
            pickle.dump({"cookies": requests.utils.dict_from_cookiejar(self.session.cookies)}, ff)

    def __reload_cookie__(self):
        print(">>>> Load user cookies from:", self.user_data_bak_path)
        with open(self.user_data_bak_path, "rb") as ff:
            user_data = pickle.load(ff)
        cookies = user_data.get("cookies", {})
        if not isinstance(cookies, dict):  # Old format saving a RequestsCookieJar
            cookies = requests.utils.dict_from_cookiejar(cookies)
        if "MUSIC_U" not in cookies:
            print(">>>> No MUSIC_U in saved cookies, skip")
            return None
        for kk, vv in cookies.items():
            self.session.cookies.set(kk, vv, domain=".music.163.com")
        profile = self.__check_login__()
        if profile is None:
            print(">>>> Saved cookies expired")
            self.session = self.__default_seesion__()
        return profile

    def get(self, url):
        return self.session.get(url)

    def post(self, url, data=None, timeout=30):
        return self.session.post(url, data=data, timeout=timeout)

    def weapi_post(self, url, params=None, timeout=30):
        from encrypt import encrypted_request

        csrf = self.session.cookies.get("__csrf", "")
        params = dict(params or {}, csrf_token=csrf)
        return self.session.post(url, params={"csrf_token": csrf}, data=encrypted_request(params), timeout=timeout)


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
    song_info["title"] = rr["songs"][0]["name"]
    song_info["artist"] = ",".join([ii["name"] for ii in rr["songs"][0]["ar"]])
    song_info["album"] = rr["songs"][0]["al"]["name"]
    try:
        song_info["track_num"] = (int(rr["songs"][0]["no"]), int(rr["songs"][0]["cd"]))
    except (ValueError, TypeError):
        song_info["track_num"] = (0, 0)
    song_info["cover_image"] = rr["songs"][0]["al"]["picUrl"]
    song_info["id"] = song_id

    album_detail = netease_get_album_detial(rr["songs"][0]["al"]["id"])
    publish_time = int(rr["songs"][0]["publishTime"])
    if publish_time == 0:
        publish_time = int(album_detail["album"]["publishTime"])
    song_info["year"] = str(datetime.fromtimestamp(publish_time / 1000).year)
    song_info["album_artist"] = album_detail["album"]["artist"].get("name", song_info["artist"])
    return song_info, rr


def detect_netease_music_name_list(song_list):
    for song_id in song_list:
        ss, rr = detect_netease_music_name(song_id)
        ss.update({"song_id": song_id})
        yield ss


def netease_parse_playlist_2_list(playlist_id):
    global global_requests_func
    if global_requests_func is None:
        global_requests_func = Requsets_with_login()

    # url_playlist_base = "http://music.163.com/api/playlist/detail?id={}"
    # url_playlist_base = "http://localhost:3000/playlist/detail?id={}"
    url_playlist_base = "https://music.163.com/api/v6/playlist/detail?id={}"
    url_playlist = url_playlist_base.format(playlist_id)

    ret = global_requests_func.post(url_playlist)
    assert ret.ok and ret.json()["code"] == 200

    play_list = ret.json()["playlist"]["trackIds"]
    for song_item in play_list:
        yield song_item["id"]


def netease_get_album_detial(album_id):
    global global_requests_func
    if global_requests_func is None:
        global_requests_func = Requsets_with_login()

    url_album_base = "http://music.163.com/api/album/{}"
    # url_album_base = "https://music.163.com/weapi/vipmall/albumproduct/detail?id={}"
    url_album = url_album_base.format(album_id)
    # resp = requests.get(url_album, headers=headers)
    resp = global_requests_func.get(url_album).json()

    if resp["code"] != 200 or "album" not in resp:
        print(">>>> ERROR: album_detail empty for album id: {}".format(album_id))
        resp = {"album": {"publishTime": datetime.now().timestamp() * 1000, "artist": {}, "songs": []}}
    return resp


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
            song_info["title"] = song_item["track"]["name"]
            song_info["artist"] = ",".join([ii["name"] for ii in song_item["track"]["artists"]])
            song_info["album"] = song_item["track"]["album"]["name"]
            song_info["track_num"] = (int(song_item["track"]["position"]), int(song_item["track"]["cd"]))
            song_info["id"] = song_item["track"]["id"]
            song_info["cover_image"] = song_item["track"]["album"]["picUrl"]
            song_info["url"] = song_item.get("lastPlayInfo", {}).get("retJson", {}).get("url", None)

            album_detail = netease_get_album_detial(song_item["track"]["album"]["id"])
            # print(url_album, album_detail["code"])
            song_info["year"] = str(datetime.fromtimestamp(int(album_detail["album"]["publishTime"]) / 1000).year)
            song_info["album_artist"] = album_detail["album"]["artist"].get("name", song_info["artist"])
            yield song_info


def generate_target_file_name(dist_path, title, artist, song_format="mp3"):
    aa = artist.replace(os.sep, " ").replace(":", " ").replace("?", " ").replace("!", " ").replace("\"", "").strip()
    tt = title.replace(os.sep, " ").replace(":", " ").replace("?", " ").replace("!", " ").replace("\"", "").replace("\xa0", " ").strip()
    dist_name = os.path.join(dist_path, "%s - %s" % (aa, tt)) + "." + song_format

    return dist_name


def download_image(pic_url, SAVE_COVER_IAMGE_SIZE=320):
    success = False
    while not success:
        try:
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

            success = True
        except:
            print(f">>>> Image decode error, try again... pic_url={pic_url}")
            sleep(1)

    buf = io.BytesIO()
    dd.save(buf, format="JPEG")
    return buf.getvalue()


def netease_cache_rename_single(song_info, file_path, dist_path, KEEP_SOURCE=True, song_format="mp3", SAVE_COVER_IAMGE_SIZE=320):
    if not os.path.exists(dist_path):
        os.makedirs(dist_path, exist_ok=True)

    if isinstance(song_info, dict):
        song_id = song_info["id"]
    else:
        song_id = song_info
        song_info, _ = detect_netease_music_name(song_id)
    try:
        tt = eyed3.load(file_path)
        # if tt is None:
        #     from mutagen.id3 import ID3
        #
        #     audio = ID3()
        #     audio.save(file_path, v2_version=3)
        #     tt = eyed3.load(file_path)
        #     tt.tag.clear()
        #     tt.tag.save()

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
            jpeg_buffer = download_image(song_info["cover_image"], SAVE_COVER_IAMGE_SIZE=SAVE_COVER_IAMGE_SIZE)
            tt.tag.images.set(3, jpeg_buffer, "image/jpeg", "album cover")
        tt.tag.save(encoding="utf8")
    except UnicodeDecodeError as err:
        print("EyeD3 decode error: %s" % err)
    except AttributeError as err:
        print("EyeD3 reading error: %s" % err)

    dist_name = generate_target_file_name(dist_path, song_info["title"], song_info["artist"], song_format)
    if dist_name != file_path:
        if KEEP_SOURCE == True:
            shutil.copyfile(file_path, dist_name)
        else:
            os.rename(file_path, dist_name)

    return dist_name


def uc_cache_decode(origin_filepath, result_filepath):
    CODE = 0xA3
    if os.path.exists(result_filepath):
        return

    with open(origin_filepath, "rb") as ff:
        music = ff.read()
    print(f"Decoding {origin_filepath}, Source file length: {len(music)}")
    music_decode = bytearray()
    for i, byte in enumerate(music):
        sys.stdout.write("\rProgress: %d%%" % (round((i + 1) * 100 / len(music))))
        sys.stdout.flush()
        if type(byte) == str: # For Python 2
            music_decode.append(int(byte.encode("hex"), 16) ^ CODE)
        else: # For Python 3
            music_decode.append(byte ^ CODE)

    print()
    with open(result_filepath, "wb") as ff:
        ff.write(music_decode)


def netease_cache_rename(source_path, dist_path, KEEP_SOURCE=True):
    for file_name in os.listdir(source_path):
        source_file_path = os.path.join(source_path, file_name)
        if file_name.endswith(".uc"):
            decode_file_name = os.path.splitext(file_name)[0] + ".mp3"
            uc_cache_decode(source_file_path, os.path.join(source_path, decode_file_name))
            file_name = decode_file_name
            ffmpeg_command = f"ffmpeg -i {file_name} -c:a libmp3lame -q:a 2 -id3v2_version 3 -write_id3v1 1 fixed_{file_name}"
            print(f">>>> Currently uc cache decoded can be not MP3. It may be AAC format.")
            print(f"     Needs to run ffmpeg commant first: {ffmpeg_command}")
            print()
            continue
        elif not file_name.endswith(".mp3"):
            continue
        if not len(file_name.split("-")) == 3:
            print(">>>> File %s not in format <song id>-<bite rate>-<random number>.mp3" % (file_name))
            continue

        song_id = file_name.split("-")[0]
        netease_cache_rename_single(song_id, source_file_path, dist_path, KEEP_SOURCE)


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
