# -*- coding: utf-8 -*-

import os
import json

import xbmcaddon

from collections import OrderedDict

from lib.constants import *
from lib.common import base_url_remove, translate_path, ensure_path_exists, generate_md5
from lib.common import file_read, file_write

ADDON = xbmcaddon.Addon()

RW_FILE = translate_path(os.path.join(ADDON.getAddonInfo('profile'), 'recently_watched.dat'))

def recently_watched_load():

    """ load recently watched from file into a variable """

    if os.path.exists( RW_FILE ):

        rw_str = file_read( RW_FILE )
        if rw_str:
            return json.load( rw_str, object_pairs_hook=OrderedDict )

    else:
        ensure_path_exists( ADDON.getAddonInfo('profile') )

    return OrderedDict({})

def recently_watched_add( name, url ):

    """ add to recently watched """

    url = base_url_remove( BASEURL, url )

    if name and url:
        data = recently_watched_load()

        title_hash = generate_md5(url)

        # if exists, remove to ensure it get put at the end
        if data.get( title_hash, False ):
            del data[title_hash]

        data[title_hash] = { 'name': name, 'url': url }
        file_write( RW_FILE, json.dumps(data) )

        return True

    return False

def recently_watched_remove( url ):

    """ remove from recently watched """

    url = base_url_remove( BASEURL, url )

    if url:

        removed = False
        data = recently_watched_load()

        title_hash = generate_md5(url)

        # if exists, remove
        if data.get( title_hash, False ):
            del data[title_hash]
            removed = True

        file_write( RW_FILE, json.dumps(data) )

        return removed

    return False
