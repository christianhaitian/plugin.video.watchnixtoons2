# -*- coding: utf-8 -*-

import os
import json

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import six
from six.moves import urllib_parse

try:
    import md5
except ImportError:
    from hashlib import md5

from lib.constants import PLUGIN_URL, RESOURCE_URL, KODI_VERSION

ADDON = xbmcaddon.Addon()

def getWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    data = window.getProperty(prop)
    return json.loads(data) if data else None

def setWindowProperty(prop, data):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    temp = json.dumps(data)
    window.setProperty(prop, temp)

def clearWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    window.clearProperty(prop)

def testWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    return window.getProperty(prop) != ''

def getRawWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    return window.getProperty(prop)

def setRawWindowProperty(prop, data):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    window.setProperty(prop, data)

def setViewMode():
    if ADDON.getSetting('useViewMode') == 'true':
        view_mode_id = ADDON.getSetting('viewModeID')
        if view_mode_id.isdigit():
            xbmc.executebuiltin('Container.SetViewMode(' + view_mode_id + ')')

def unescapeHTMLText(text):

    """
    Unescape HTML entities.
    Strings found by regex-searching on all lists in the source website.
    It's very likely to only be these.
    """

    if isinstance(text, six.text_type) and six.PY2:
        text = text.encode('utf-8')

    if r'&' in text:
        text = text.replace(r'&amp;', '&').replace(r'&quot;', '"').replace(r'&apos;', "'")

        if r'&#' in text:
            text = text.replace(r'&#038;', '&').replace(r'&#039;', '’').replace(r'&#160;', ' ')\
                .replace(r'&#8211;', '–').replace(r'&#8216;', '‘').replace(r'&#8217;', '’')\
                .replace(r'&#8220;', '“').replace(r'&#8221;', '”').replace(r'&#8230;', '…')

    return text.replace('\u2606', ' ')

def base_url_remove( base_url, url ):

    """ ensures the base URL is removed from a URL"""

    if url.startswith( base_url ):
        url = url.replace( base_url, '', 1 )

    return url

def ensure_url_schema( url ):

    """ returns a url that has https """

    if url:
        if url.startswith('//'):
            return 'https:' + url

    return url


def ensure_full_url( base_url, url ):

    """ returns a full url """

    if url:
        url = ensure_url_schema( url )
        if url.startswith('http'):
            return url
        if url.startswith('/'):
            return base_url + url

    return url

def ensure_current_domain( url, domain, domains ):

    """ returns a full url with the current domain """

    url = ensure_full_url( 'https://' + domain, url )
    for d in domains:
        if d in url:
            return url.replace( d, domain, 1 )

    return url

def xbmc_debug(*args):

    """ used for debugging """

    xbmc.log(
        'WatchNixtoons2 > '+' '.join((val if isinstance(val, str) else repr(val)) for val in args),
        xbmc.LOGWARNING
    )

def item_set_info( line_item, properties ):

    """
    line item set info
    Fix listitem deprecated warnings
    """

    if KODI_VERSION > 19.8:
        vidtag = line_item.getVideoInfoTag()
        if properties.get( 'title' ):
            vidtag.setTitle( properties.get( 'title' ) )
        if properties.get( 'plot' ):
            vidtag.setPlot( properties.get( 'plot' ) )
        if properties.get( 'tvshowtitle' ):
            vidtag.setTvShowTitle( properties.get( 'tvshowtitle' ) )
        if properties.get( 'season' ):
            vidtag.setSeason( properties.get( 'season' ) )
        if properties.get( 'episode' ):
            vidtag.setEpisode( properties.get( 'episode' ) )
        if properties.get( 'mediatype' ):
            vidtag.setMediaType( properties.get('mediatype') )
    else:
        line_item.setInfo('video', properties)

def translate_path(path):

    """
    method to translate path for both PY2 & PY3
    stops all the if else statements
    """

    if six.PY2:
        return xbmc.translatePath( path )
    return xbmcvfs.translatePath( path )

def ensure_path_exists(path):

    """ creates path if doesn't exist """

    addon_data_path = translate_path(path)

    if os.path.exists(addon_data_path) is False:
        os.mkdir(addon_data_path)
        xbmc.sleep(1)
        return True

    return False

def generate_md5( str_to_md5 ):

    """ generates a MD5 hash """

    if six.PY2:
        md5_instance = md5.new()
    else:
        md5_instance = md5()
        str_to_md5 = bytes(str_to_md5, 'UTF-8')

    md5_instance.update(str_to_md5)
    return md5_instance.hexdigest()

def build_url(query):

    """
    Helper function to build a Kodi xbmcgui.ListItem URL.
    :param query: Dictionary of url parameters to put in the URL.
    :returns: A formatted and urlencoded URL string.
    """

    return PLUGIN_URL + '?' + \
        urllib_parse.urlencode({k: v.encode('utf-8') if isinstance(v, six.text_type)
            else unicode(v, errors='ignore').encode('utf-8')
            for k, v in query.items()})

def file_read( path ):

    """ reads file's contents """

    if six.PY2:
        return open( path, 'r' )

    return open( path, 'r', encoding='utf8'  )

def file_write( path, content ):

    """ writes file's contents """

    if six.PY2:
        file_str = open( path, 'w' )
        file_str.write( content )
        file_str.close()
        return True

    with open( path, 'w', encoding='utf8' ) as file_str:
        file_str.write( content )
        file_str.close()
        return True

def hash_file_get( path, file_dir = 'thumbnail' ):

    """ gets required hash file """

    hashes = file_read(
        translate_path( RESOURCE_URL + 'data/' + file_dir + '/' + path.replace('/','') + '.json' )
    )

    if hashes:
        return json.load( hashes )

    return {}

def quality_label( quality ):

    """ Retrieves label based upon quality """

    if quality >= 1080:
        return '1080 (FHD)'
    if quality >= 720:
        return '720 (HD)'
    return '480 (SD)'

if six.PY3:
    xrange = range
