import requests

headers_baidu = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.115 Safari/537.36"
}
headers_qq = {
    "referer": "https://y.qq.com/portal/player.html",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
}
headers_migu = {
    "referer": "http://music.migu.cn/",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
}
headers_kugou = {
    "referer": "http://m.kugou.com",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
}


def baidu_search_single(keyword, page_size=5, pick=0):
    url_suggestion = "http://musicapi.qianqian.com/v1/restserver/ting"
    params = {"query": keyword, "method": "baidu.ting.search.common", "format": "json", "page_no": 1, "page_size": page_size}
    resp = requests.get(url_suggestion, params=params, headers=headers_baidu)

    song_info = resp.json()
    if song_info == None or len(song_info.get("song_list", [])) == 0:
        print(">>>> song info not found, keyword = %s" % keyword)
        return None

    songs = song_info["song_list"]
    print([(id, ii["title"].replace("<em>", "").replace("</em>", ""), ii["author"]) for id, ii in enumerate(songs)])
    song_id_baidu = songs[pick]["song_id"]
    print(">>>> keyword = %s, song_id_baidu = %s" % (keyword, song_id_baidu))

    return song_id_baidu


def baidu_download_single_flac(keyword, page_size=5, pick=0):
    song_id_baidu = baidu_search_single(keyword, page_size, pick)
    if song_id_baidu == None:
        print(">>>> Baidu songid not found, keyword = %s" % keyword)
        return None, None, None, None

    url_base = "http://music.baidu.com/data/music/fmlink"
    params = {"songIds": song_id_baidu, "type": "flac"}
    resp = requests.get(url_base, params=params, headers=headers_baidu)
    resp_json = resp.json()
    if resp_json["errorCode"] != 22000 or "data" not in resp_json or resp_json["data"] == "":
        print(">>>> No data found, song_id_baidu = %s" % (song_id_baidu))
        return None, None, None, None

    song_artist = resp_json["data"]["songList"][0]["artistName"]
    song_name = resp_json["data"]["songList"][0]["songName"]
    download_url = resp_json["data"]["songList"][0]["songLink"]
    if download_url == None or len(download_url) < 4:
        print(">>>> download_url is None, maybe it is limited by copyright. keyword = %s" % keyword)
        return None, None, None, None
    song_format = resp_json["data"]["songList"][0]["format"]
    # print("song_format = %s, url_download = %s" % (song_format, download_url))
    return download_url, song_name, song_artist, song_format


def baidu_download_single_mp3(keyword, page_size=5, pick=0):
    song_id_baidu = baidu_search_single(keyword, page_size, pick)
    if song_id_baidu == None:
        print(">>>> Baidu songid not found, keyword = %s" % keyword)
        return None, None, None, None

    url_base = "http://tingapi.ting.baidu.com/v1/restserver/ting"
    params = {"method": "baidu.ting.song.play", "bit": 320, "songid": song_id_baidu}
    resp = requests.get(url_base, params=params, headers=headers_baidu)
    resp_json = resp.json()
    if resp_json["error_code"] != 22000 or resp_json.get("songinfo", "") == "" or resp_json.get("bitrate", "") == "":
        print(">>>> No data found, song_id_baidu = %s" % (song_id_baidu))
        return None, None, None, None

    song_artist = resp_json["songinfo"]["author"]
    song_name = resp_json["songinfo"]["title"]
    download_url = resp_json["bitrate"]["file_link"]
    if download_url == None or len(download_url) < 4:
        print(">>>> download_url is None, maybe it is limited by copyright. keyword = %s" % keyword)
        return None, None, None, None
    song_format = resp_json["bitrate"]["file_extension"]
    # print("song_format = %s, url_download = %s" % (song_format, download_url))

    return download_url, song_name, song_artist, song_format


def qq_search_single(keyword, page_size=5, pick=0):
    url_suggestion = "http://c.y.qq.com/soso/fcgi-bin/search_for_qq_cp"
    params = {"w": keyword, "format": "json", "p": 1, "n": page_size}
    resp = requests.get(url_suggestion, params=params, headers=headers_qq)
    song_info = resp.json()
    if song_info == None or "data" not in song_info or len(song_info["data"]) == 0:
        print(">>>> song info not found, keyword = %s" % keyword)
        return None, None, None

    songs = song_info.get("data", {}).get("song", {}).get("list", [])
    if len(songs) == 0:
        print(">>>> song info not found, keyword = %s" % keyword)
        return None, None, None

    print([(id, ii["songname"], " ".join([ss["name"] for ss in ii["singer"]])) for id, ii in enumerate(songs)])
    song_id_qq = songs[pick]["songmid"]
    song_name_qq = songs[pick]["songname"]
    song_artist_qq = " ".join([ss["name"] for ss in songs[pick]["singer"]])
    print(">>>> keyword = %s, song_artist_qq = %s, song_name_qq = %s" % (keyword, song_artist_qq, song_name_qq))

    return song_id_qq, song_name_qq, song_artist_qq


def qq_download_single(keyword, page_size=5, pick=0):
    import random

    song_id_qq, song_name, song_artist = qq_search_single(keyword, page_size, pick)
    if song_id_qq == None:
        print(">>>> QQ songid not found, song_name = %s" % song_name)
        return None, None, None, None

    guid = str(random.randrange(1000000000, 10000000000))
    params = {
        "guid": guid,
        "loginUin": "3051522991",
        "format": "json",
        "platform": "yqq",
        "cid": "205361747",
        "uin": "3051522991",
        "songmid": song_id_qq,
        "needNewCode": 0,
    }
    rate_list = [("A000", "ape", 800), ("F000", "flac", 800), ("M800", "mp3", 320), ("M500", "mp3", 128)]
    for rate in rate_list:
        params["filename"] = "%s%s.%s" % (rate[0], song_id_qq, rate[1])
        resp = requests.get("https://c.y.qq.com/base/fcgi-bin/fcg_music_express_mobile3.fcg", params=params)
        vkey = resp.json().get("data", {}).get("items", [])[0].get("vkey", "")
        if vkey != "":
            break

    if vkey == "":
        print(">>>> Download vkey not found, keyword = %s" % keyword)
        return None, None, None, None

    url_base = "http://dl.stream.qqmusic.qq.com/{}?vkey={}&guid={}&uin=3051522991&fromtag=64"
    download_url = url_base.format(params["filename"], vkey, guid)
    song_format = rate[1]

    return download_url, song_name, song_artist, song_format


def migu_search_single(keyword, page_size=5, pick=0):
    url_suggestion = "http://pd.musicapp.migu.cn/MIGUM2.0/v1.0/content/search_all.do"
    payload = {
        "ua": "Android_migu",
        "version": "5.0.1",
        "text": keyword,
        "pageNo": 1,
        "pageSize": page_size,
        "searchSwitch": '{"song":1,"album":0,"singer":0,"tagSong":0,"mvSong":0,"songlist":0,"bestShow":1}',
    }

    resp = requests.get(url_suggestion, params=payload, headers=headers_migu)
    song_info = resp.json()
    if song_info["code"] != "000000":
        print(">>>> song info not found, keyword = %s" % keyword)
        return None, None, None, None

    songs = song_info.get("songResultData", {}).get("result", [])
    if len(songs) == 0:
        print(">>>> song info not found, keyword = %s" % keyword)
        return None, None, None, None

    print([(id, ii["name"], " ".join([ss["name"] for ss in ii["singers"]])) for id, ii in enumerate(songs)])
    song_id_migu = songs[pick]["contentId"]
    song_name_migu = songs[pick]["name"]
    song_artist_migu = " ".join([ss["name"] for ss in songs[pick]["singers"]])
    rate_list = sorted(songs[pick].get("rateFormats", []), key=lambda x: int(x["size"]), reverse=True)
    print(">>>> keyword = %s, song_id_migu = %s" % (keyword, song_id_migu))

    return song_id_migu, song_name_migu, song_artist_migu, rate_list[0]


def migu_download_single(keyword, page_size=5, pick=0):
    song_id_migu, song_name, song_artist, rate = migu_search_single(keyword, page_size, pick)
    if song_id_migu == None:
        print(">>>> MIGU songid not found, keyword = %s" % keyword)
        return None, None, None, None

    url_base = "http://app.pd.nf.migu.cn/MIGUM2.0/v1.0/content/sub/listenSong.do?toneFlag={}&netType=00&userId={}&ua=Android_migu&version=5.1&copyrightId=0&contentId={}&resourceType={}&channel=0"
    userId = "15548614588710179085069"
    download_url = url_base.format(rate.get("formatType", "SQ"), userId, song_id_migu, rate.get("resourceType", "E"))

    song_format_default = "flac" if rate.get("formatType", "") == "SQ" else "mp3"
    song_format = rate.get("fileType", song_format_default)

    return download_url, song_name, song_artist, song_format


def kugou_search_single(keyword, page_size=5, pick=0):
    url_suggestion = "http://songsearch.kugou.com/song_search_v2"
    payload = {"keyword": keyword, "platform": "WebFilter", "format": "json", "page": 1, "pagesize": page_size}
    resp = requests.get(url_suggestion, params=payload, headers=headers_kugou)
    song_info = resp.json()
    if song_info["status"] != 1:
        print(">>>> song info not found, keyword = %s" % keyword)
        return [], None, None

    songs = song_info.get("data", {}).get("lists", [])
    if len(songs) == 0:
        print(">>>> song info not found, keyword = %s" % keyword)
        return [], None, None

    print([(id, ii["SongName"], ii["SingerName"]) for id, ii in enumerate(songs)])
    song_name_kugou = songs[pick]["SongName"]
    song_artist_kugou = songs[pick]["SingerName"]
    song_id_kugou = []
    keys_list = ["SQFileHash", "HQFileHash", "FileHash"]
    for key in keys_list:
        hash = songs[pick].get(key, "")
        if hash and len(hash) != 0 and hash != "0" * 32:
            song_id_kugou.append(hash)
    print(">>>> keyword = %s, song_id_kugou = %s" % (keyword, song_id_kugou))

    return song_id_kugou, song_name_kugou, song_artist_kugou


def kugou_download_single(keyword, page_size=5, pick=0):
    song_id_kugou, song_name, song_artist = kugou_search_single(keyword, page_size, pick)
    if len(song_id_kugou) == 0:
        print(">>>> KUGOU songid not found, song_name = %s" % song_name)
        return None, None, None, None

    url_base = "http://m.kugou.com/app/i/getSongInfo.php"

    for hash in song_id_kugou:
        payload = {"cmd": "playInfo", "hash": hash}
        resp = requests.get(url_base, params=payload, headers=headers_kugou)
        resp_json = resp.json()
        download_url = resp_json.get("url", "")
        song_format = resp_json.get("extName", "mp3")
        if len(download_url) != 0:
            break

    if len(download_url) == 0:
        return None, None, None, None
    else:
        return download_url, song_name, song_artist, song_format
