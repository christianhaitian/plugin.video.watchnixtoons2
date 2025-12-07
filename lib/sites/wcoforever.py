
SITE_SETTINGS = {
    'catalog': {
        'regex': r'''<li(?:\sdata\-id=\"[0-9]+\")?>\s*<a href="([^"]+).*?>([^<]+)''',
        'start': '"ddmcc"',
        'start_alt': False,
        'end': '<script>',
    },
    'episode': {
        'regex': r'''<a href=\"(?P<link>[^\"]+).*?(data-lang=\"(?P<type>[^\"]+)\")?>(?:<span>)?(?P<name>[^<]+)''',
        'start': 'name="pid"',
        'end': '"sidebar-all"',
    },
    'series_search': {
        'regex': r'''<a\s*href=\"(?P<link>[^\"]+).*?>([^<]+)\s*<img alt=\"(?P<name>[^\"]+)\"\s*src=\"(?P<img>[^\"]+)''',
        'start': 'submit',
        'end': '<script>',
    },
    'episode_search': {
        'regex': '''<a href="([^"]+)[^>]*>([^<]+)</a''',
        'start': 'submit',
        'end': 'cizgiyazisi',
    },
    'genre': {
        'regex': '''href=\"([^\"]+)\"\s*class=\"genre-buton\">\s*<span(?:[^>]+)>(.*?)</''',
        'start': r'sidebar_cat',
        'end': r'class="recent-release-main"',
    },
    'thumbnail': {
        'regex': '',
        'start': 'og:image" content="',
        'end': '',
    },
    'page_meta': {
        'regex': 'href="([^"]+)',
        'start': '"header-tag"',
        'end': '',
    },
    'page_plot': {
        'regex': r'</h3>\s*<p>(.*?)</p>',
        'start': 'Info:',
        'end': '',
    },
    'latest': {
        'url': '/last-50-recent-release',
        'regex': r'''src=\"(?P<img>[^\"]+)\">\s*</a>\s*</div>\s*<div\s*class=\"recent-release-episodes\"><a\s*href=\"(?P<link>[^\"]+)\"\s*rel=\"bookmark\">(?P<name>.*?)</a''',
        'start': 'class="recent-release-main"',
        'end': '</body>',
    },
    'latest_movies': {
        'regex': '''<a href="([^"]+).*?>([^<]+)''',
        'start': '"sidebar_right3"',
        'end': '"sidebar-all"',
    },
    'popular': {
        'regex': '''<a href="([^"]+).*?>([^<]+)''',
        'start': '"sidebar-titles"',
        'end': '</div>',
    },
    'parent': {
        'regex': r'<h2><a href=\"([^\"]+)\"(?:[^\>]+)?><span(?:[^\>]+)>([^/<]+)<',
        'start': '"header-tag"',
        'end': '',
    },
    'chapter': {
        'regex': r'onclick=\"myFunction.*<script',
    }
}

DECODE_SOURCE_REQUIRED = True

def premium_workaround_check( html, urls ):

    """ checks if there is a work around for current domain """

    return False
