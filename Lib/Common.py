# -*- coding: utf-8 -*-
import json
import xbmc, xbmcgui, xbmcaddon
import xbmcvfs
import six

try:
    import md5
except ImportError:
    from hashlib import md5

ADDON = xbmcaddon.Addon()
KODI_VERSION = float(xbmcaddon.Addon('xbmc.addon').getAddonInfo('version')[:4])

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
        viewModeID = ADDON.getSetting('viewModeID')
        if viewModeID.isdigit():
            xbmc.executebuiltin('Container.SetViewMode(' + viewModeID + ')')


def unescapeHTMLText(text):
    if isinstance(text, six.text_type) and six.PY2:
        text = text.encode('utf-8')
    # Unescape HTML entities.
    if r'&#' in text:
        # Strings found by regex-searching on all lists in the source website. It's very likely to only be these.
        text = text.replace(r'&#8216;', '‘').replace(r'&#8221;', '”').replace(r'&#8211;', '–').replace(r'&#038;', '&')\
        .replace(r'&#8217;', '’').replace(r'&#8220;', '“').replace(r'&#8230;', '…').replace(r'&#160;', ' ')

    return text.replace(r'&amp;', '&').replace(r'&quot;', '"').replace('\u2606', ' ')


def xbmcDebug(*args):
    xbmc.log('WatchNixtoons2 > ' + ' '.join((val if isinstance(val, str) else repr(val)) for val in args), xbmc.LOGWARNING)


# line item set info
# Fix listitem deprecated warnings
def item_set_info( line_item, properties ):
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
    else:
        line_item.setInfo('video', properties)


# method to translate path for both PY2 & PY3
# stops all the if else statements
def translate_path(path):
    if six.PY2:
        return xbmc.translatePath( path )
    else:
        return xbmcvfs.translatePath( path )


# generates a MD5 hash
def generateMd5(strToMd5):

    if six.PY2:
        md5Instance = md5.new()
    else:
        md5Instance = md5()
        strToMd5 = bytes(strToMd5, 'UTF-8')

    md5Instance.update(strToMd5)
    return md5Instance.hexdigest()

def quality_label( quality ):

    """ Retrieves label based upon quality """

    if quality >= 1080:
        return '1080 (FHD)'
    if quality >= 720:
        return '720 (HD)'
    return '480 (SD)'

def xbmc_debug(*args):

    """ used for debugging """

    xbmc.log(
        'WatchNixtoons2 > '+' '.join((val if isinstance(val, str) else repr(val)) for val in args),
        xbmc.LOGWARNING
    )