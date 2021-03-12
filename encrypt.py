# -*- coding: utf-8 -*-

import os
import base64
import json
import binascii
from Crypto.Cipher import AES

# Encrypt key
modulus = "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
nonce = b"0CoJUm6Qyw8W8jud"
pub_key = "010001"


def encrypted_request(text):
    text = json.dumps(text)
    sec_key = create_secret_key(16)
    enc_text = aes_encrypt(aes_encrypt(text, nonce), sec_key)
    enc_sec_key = rsa_encrypt(sec_key, pub_key, modulus)
    data = {"params": enc_text, "encSecKey": enc_sec_key}
    return data


def aes_encrypt(text, sec_key):
    pad = 16 - len(text) % 16
    text = text + chr(pad) * pad
    encryptor = AES.new(sec_key, 2, b"0102030405060708")
    cipher_text = encryptor.encrypt(text.encode())
    cipher_text = base64.b64encode(cipher_text).decode("utf-8")
    return cipher_text


def rsa_encrypt(text, public_key, p_modulus):
    text = text[::-1]
    rs = pow(int(binascii.hexlify(text), 16), int(public_key, 16), int(p_modulus, 16))
    return format(rs, "x").zfill(256)


def create_secret_key(size):
    return binascii.hexlify(os.urandom(size))[:16]
