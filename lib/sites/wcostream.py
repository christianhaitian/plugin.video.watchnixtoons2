import re
import six

from lib.constants import *
from lib.network import request_helper

SITE_SETTINGS = {
    'catalog': {
        'regex': r'''<li(?:\sdata\-id=\"[0-9]+\")?>\s*<a href=\"([^\"]+)\".*?>([^<]+)''',
        'start': '"anime-search"',
        'start_alt': '<div class="clear">',
        'end': '"bartitle"',
    },
    'episode': {
        'regex': r'''<a href=\"(?P<link>[^\"]+).*?(data-lang=\"(?P<type>[^\"]+)\")?>(?:<span>)?(?P<name>[^<]+)''',
        'start': 'name="pid"',
        'end': '<!--CAT PAGE',
    },
    'series_search': {
        'regex': r'''<a href="(?P<link>[^"]+).*?>(?P<name>[^<]+)</a>(?P<img>)''',
        'start': 'aramamotoru',
        'end': 'cizgiyazisi',
    },
    'episode_search': {
        'regex': '''<a href="([^"]+)[^>]*>([^<]+)</a''',
        'start': 'submit',
        'end': 'cizgiyazisi',
    },
    'genre': {
        'regex': '''<a.*?"([^"]+).*?>(.*?)</''',
        'start': r'ddmcc">',
        'end': r'</div></div>',
    },
    'thumbnail': {
        'regex': '',
        'start': 'og:image" content="',
        'end': '',
    },
    'page_meta': {
        'regex': 'href="([^"]+)',
        'start': 'class="lalyx"',
        'end': '',
    },
    'page_plot': {
        'regex': r'class=\"iltext\"><p>(.*?)</p>',
        'start': 'katcont',
        'end': '',
    },
    'latest': {
        'url': '',
        'regex': r'''src=\"(?P<img>[^\"]+)\">\s*</a>\s*</div>\s*<div class=\"recent-release-episodes\">\s*<a href=\"(?P<link>[^\"]+)\" rel=\"bookmark\">(?P<name>[^<]+)</a>''',
        'start': '<div class="recent-release">',
        'end': '</ul>',
    },
    'latest_movies': {
        'regex': '''<li><a href="([^"]+).*?>([^<]+)''',
        'start': '"cat-listview cat-listbsize"',
        'end': '</ul>',
    },
    'popular': {
        'regex': '''<a href="([^"]+).*?>([^<]+)''',
        'start': 'class="menustyle">',
        'end': '</div>',
    },
    'parent': {
        'regex': r'class=\"ildate\">\s*<a href=\"([^\"]+)\"(?:[^\>]+)?><span(?:[^\>]+)>([^/<]+)<',
        'start': '"lalyx"',
        'end': '',
    },
    'chapter': {
        'regex': r'<iframe id=\"(?:[a-zA-Z]+)uploads(?:[0-9]+)\" src=\"([^\"]+)\"',
    }
}

DECODE_SOURCE_REQUIRED = False

def premium_workaround_check( html, urls ):

    """ checks if there is a work around for current domain """

    # get playlist link
    playlist_url = re.search(r'<a href="([^"]+)">Watch on Playlist</a>', html)

    if playlist_url:
        playlist_url = playlist_url.group(1).replace( '/playlist-cat/', '/playlist-cat-jw/' )
        playlist_url = playlist_url.replace( BASEDOMAIN, DOMAINS[2] ) if playlist_url.startswith('http') else 'https://' + DOMAINS[2] + playlist_url
        html = request_helper(playlist_url).text
        media_id = re.search(r'if\s*\(mediaid === \"([0-9]+)\"\)', html)
        if media_id:
            media_id = media_id.group(1)
            playlist_url = re.search(r'playlist: \"(/playlist-cat-rss/[0-9]+\?[^\"]+)\",', html)
            if playlist_url:
                playlist_url = playlist_url.group(1)
                playlist_url = playlist_url.replace( DOMAINS[2], BASEDOMAIN ) if playlist_url.startswith('http') else BASEURL + playlist_url
                rss = request_helper(playlist_url).text
                video_url = re.search(r'<mediaid>' + six.ensure_str( media_id ) + r'</mediaid>\s*<jwplayer:image>(?:[^<]+)</jwplayer:image>\s*<jwplayer:source file=\"([^\"]+)\"', rss)
                if video_url:
                    urls[ 'stream' ] = video_url.group(1)
                    return urls

    return False
