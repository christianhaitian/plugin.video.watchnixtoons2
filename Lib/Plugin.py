# -*- coding: utf-8 -*-
import re
import sys
import requests
import json #added by Christian Haitian
import os #added by Christian Haitian
import pickle as pickle #added by Christian Haitian
import datetime #added by Christian Haitian
from urllib.parse import urlparse, urljoin #added by Christian Haitian

from itertools import chain
from base64 import b64decode
from time import time, sleep
from urllib.parse import parse_qsl
from string import ascii_uppercase
from urllib.parse import quote_plus, urlencode
from os import sep as osSeparator #added by Christian Haitian

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

from Lib.Common import *
from Lib.SimpleTrakt import SimpleTrakt

# Disable urllib3's "InsecureRequestWarning: Unverified HTTPS request is being made" warnings
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from functools import reduce
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

global MEDIA_HEADERS

PLUGIN_ID = int(sys.argv[1])
PLUGIN_URL = sys.argv[0]

#Mod by Christian Haitian starts here
ADDON = xbmcaddon.Addon()
if (not (ADDON.getSetting('watchnixtoons2.name') and not ADDON.getSetting('watchnixtoons2.name').isspace())):
    BASEURL = 'https://www.thewatchcartoononline.tv'
else:
    BASEURL = 'https://user.wco.tv'
#Mod by Christian Haitian ends here

# Due to a recent bug on the server end, the mobile URL is now only used on 'makeLatestCatalog()'.
BASEURL_MOBILE = 'https://m.wcostream.com' # Mobile version of one of their domains (seems to be the only one).

PROPERTY_CATALOG_PATH = 'wnt2.catalogPath'
PROPERTY_CATALOG = 'wnt2.catalog'
PROPERTY_EPISODE_LIST_URL = 'wnt2.listURL'
PROPERTY_EPISODE_LIST_DATA = 'wnt2.listData'
PROPERTY_LATEST_MOVIES = 'wnt2.latestMovies'
PROPERTY_INFO_ITEMS = 'wnt2.infoItems'
PROPERTY_SESSION_COOKIE = 'wnt2.cookie'

#Mod by Christian Haitian starts here
#Define addon plugin directory
if BASEURL == 'https://user.wco.tv':
    Data_Dir = os.path.join(xbmcaddon.Addon().getAddonInfo('path'))
    login = ADDON.getSetting('watchnixtoons2.name')
    password = ADDON.getSetting('watchnixtoons2.password')
# Assuming two cookies are used for persistent login.
# (Find it by tracing the login process)
    persistentCookieNames = ['wordpress_sec_231de03aca492828e4d084c4d94c5935', 'wordpress_logged_in_231de03aca492828e4d084c4d94c5935']
    URL = 'https://user.wco.tv'
    urlData = urlparse(URL)
#Downloaded wco cookie will be stored addon plugin directory
    cookieFile = Data_Dir + osSeparator + urlData.netloc + '.cookie'
    signinUrl = urljoin(URL, "/wp-login.php")
#Check if cookie is older than 24 hours.  If so delete, it so it can be recreated.
    if os.access(cookieFile, os.F_OK):
        date_check = datetime.datetime.fromtimestamp(os.path.getmtime(cookieFile))
        if datetime.datetime.now() - date_check > datetime.timedelta(hours=24):
                os.remove(cookieFile)

#Setup wco session with a new cookie if it does not exists.
    with requests.Session() as session:
        try:
            with open(cookieFile, 'rb') as f:
                session.cookies.update(pickle.load(f))
        except Exception:
        # If could not load cookies from file, get the new ones by login in
            post = session.post(
                signinUrl,
                data={
                    'log': login,
                    'pwd': password,
                    }
            )
            try:
                with open(cookieFile, 'wb') as f:
                    jar = requests.cookies.RequestsCookieJar()
                    for cookie in session.cookies:
                        if cookie.name in persistentCookieNames:
                            jar.set_cookie(cookie)
                    pickle.dump(jar, f)
            except Exception as e:
                os.remove(cookieFile)
                raise(e)
#Mod by Christian Haitian ends here

# Show catalog: whether to show the catalog categories or to go straight to the "ALL" section with all items visible.
ADDON_SHOW_CATALOG = ADDON.getSetting('showCatalog') == 'true'
# Use Latest Releases date: whether to sort the Latest Releases items by their date, or with a catalog.
ADDON_LATEST_DATE = ADDON.getSetting('useLatestDate') == 'true'
# Use Latest Releases thumbs: whether to show a little thumbnail available for the Latest Releases items only.
ADDON_LATEST_THUMBS = ADDON.getSetting('showLatestThumbs') == 'true'
# Use poster images for each catalog folder. Makes for a better experience on custom Kodi skins.
ADDON_CATALOG_THUMBS = ADDON.getSetting('showCatalogThumbs') == 'true'
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_FANART = os.path.join(xbmcaddon.Addon().getAddonInfo('path')) + osSeparator + 'fanart.jpg'
ADDON_ICON_DICT = {'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'poster': ADDON_ICON, 'fanart': ADDON_FANART}
ADDON_TRAKT_ICON = 'special://home/addons/plugin.video.watchnixtoons2/resources/traktIcon.png'

# To let the source website know it's this plugin. Also used inside "makeLatestCatalog()" and "actionResolve()".
WNT2_USER_AGENT = 'Mozilla/5.0 (compatible; WatchNixtoons2/0.4.1; ' \
'+https://github.com/doko-desuka/plugin.video.watchnixtoons2)'

MEDIA_HEADERS = None # Initialized in 'actionResolve()'.

# Url paths: paths to parts of the website, to be added to the BASEURL url.
# Also used to tell what kind of catalog is loaded in memory.
# In case they change in the future it'll be easier to modify in here.
URL_PATHS = {
    'latest': 'latest', # No path used, 'makeLatestCatalog()' uses the homepage of the mobile website.
    'popular': 'popular', # No path used, 'makePopularCatalog()' uses the hompage of the desktop website.
    'dubbed': '/dubbed-anime-list',
    'cartoons': '/cartoon-list',
    'subbed': '/subbed-anime-list',
    'movies': '/movie-list',
    'latestmovies': '/anime/movies',
    'ova': '/ova-list',
    'search': '/search',
    'genre': '/search-by-genre'
}


def actionMenu(params):
    def _menuItem(title, data, color):
        item = xbmcgui.ListItem('[B][COLOR ' + color + ']' + title + '[/COLOR][/B]', label2 = title)
        item.setArt(ADDON_ICON_DICT)
        item.setInfo('video', {'title': title, 'plot': title})
        return (buildURL(data), item, True)

    xbmcplugin.addDirectoryItems(
        PLUGIN_ID,
        (
            _menuItem('Latest Releases', {'action': 'actionCatalogMenu', 'path': URL_PATHS['latest']}, 'mediumaquamarine'),
            _menuItem( # Make the Latest Movies menu go straight to the item list, no catalog.
                'Latest Movies', {'action': 'actionLatestMoviesMenu', 'path': URL_PATHS['latestmovies']}, 'mediumaquamarine'
            ),
            _menuItem('Popular & Ongoing Series', {'action': 'actionCatalogMenu', 'path': URL_PATHS['popular']}, 'mediumaquamarine'),
            _menuItem('Dubbed Anime', {'action': 'actionCatalogMenu', 'path': URL_PATHS['dubbed']}, 'lightgreen'),
            _menuItem('Cartoons', {'action': 'actionCatalogMenu', 'path': URL_PATHS['cartoons']}, 'lightgreen'),
            _menuItem('Subbed Anime', {'action': 'actionCatalogMenu', 'path': URL_PATHS['subbed']}, 'lightgreen'),
            _menuItem('Movies', {'action': 'actionCatalogMenu', 'path': URL_PATHS['movies']}, 'lightgreen'),
            _menuItem('OVA Series', {'action': 'actionCatalogMenu', 'path': URL_PATHS['ova']}, 'lightgreen'),
            _menuItem('Search', {'action': 'actionSearchMenu',  'path': 'search'}, 'lavender'), # Non-web path.
            _menuItem('Settings', {'action': 'actionShowSettings','path': 'settings'}, 'lavender') # Non-web path.
        )
    )
    xbmcplugin.endOfDirectory(PLUGIN_ID)


def actionCatalogMenu(params):
    xbmcplugin.setContent(PLUGIN_ID, 'tvshows')
    catalog = getCatalogProperty(params)

    if ADDON_SHOW_CATALOG:
        def _catalogMenuItemsMake():
            items = [ ]
            if ADDON_CATALOG_THUMBS:
                # The catalog folders will each get a letter image, taken from the web (this way
                # these images don't have to be distributed w/ the add-on, if they're not needed).
                # After they're downloaded, the images exist in Kodi's image cache folders.
                THUMBS_BASEURL = 'https://doko-desuka.github.io/128h/'
                artDict = {'thumb': None, 'fanart': ADDON_FANART}
                miscItem = None
                for sectionName in sorted(catalog.keys()):
                    if catalog[sectionName]:
                        item = xbmcgui.ListItem(sectionName)
                        # Correct the address for the '#' (miscellaneous, non-letter) category.
                        artDict['thumb'] = THUMBS_BASEURL + ('0' if sectionName == '#' else sectionName) + '.png'
                        item.setArt(artDict)
                        item.setInfo('video', {'plot': sectionName})
                        items.append(
                            (
                                buildURL({'action': 'actionCatalogSection', 'path': params['path'], 'section': sectionName}),
                                item,
                                True
                            )
                        )
            else:
                items = [
                    (
                        buildURL({'action': 'actionCatalogSection', 'path': params['path'], 'section': sectionName}),
                        xbmcgui.ListItem(sectionName),
                        True
                    )
                    for sectionName in sorted(catalog.keys()) if len(catalog[sectionName])
                ]
            # See if an "All" folder is necessary (when there's more than one folder in the catalog).
            if len(items) > 1:
                sectionAll = (
                    buildURL({'action': 'actionCatalogSection', 'path': params['path'], 'section': 'ALL'}),
                    xbmcgui.ListItem('All'),
                    True
                )
                if ADDON_CATALOG_THUMBS:
                    artDict['thumb'] = THUMBS_BASEURL + 'ALL.png'
                    sectionAll[1].setArt(artDict)
                    sectionAll[1].setInfo('video', {'plot': 'All'})
                return [sectionAll] + items
            else:
                return items

        items = _catalogMenuItemsMake()
        if items:
            if len(items) > 1:
                xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
            else:
                # Conveniency when a search leads to only 1 result, show it already without the catalog screen.
                params['section'] = 'ALL'
                actionCatalogSection(params)
                return
        else:
            xbmcplugin.addDirectoryItem(PLUGIN_ID, '', xbmcgui.ListItem('(No Results)'), isFolder=False)
        xbmcplugin.endOfDirectory(PLUGIN_ID)
        setViewMode()
    else:
        params['section'] = 'ALL'
        actionCatalogSection(params)


def actionCatalogSection(params):
    catalog = getCatalogProperty(params)
    path = params['path']

    # Set up a boolean indicating if the catalog items are already playable, instead of being folders
    # with more items inside.
    # This is true for the OVA, movies, latest-episodes, movie-search and episode-search catalogs.
    # Items in these catalogs link to the video player pages already.
    isSpecial = (
        path in {URL_PATHS['ova'], URL_PATHS['movies'], URL_PATHS['latest']}
        or params.get('searchType', 'series') != 'series' # not series = movies or episodes search
    )

    if isSpecial:
        action = 'actionResolve'
        isFolder = False
    else:
        action = 'actionEpisodesMenu'
        isFolder = True

    thumb = params.get('thumb', ADDON_ICON)
    if path != URL_PATHS['latest'] or not ADDON_LATEST_THUMBS:
        artDict = {'icon': thumb, 'thumb': thumb, 'poster': thumb} if thumb else None
    else:
        artDict = {'icon': thumb, 'thumb': 'DefaultVideo.png', 'poster': 'DefaultVideo.png', 'fanart': thumb} if thumb else None

    # Persistent property with item metadata, used with the "Show Information" context menu.
    infoItems = getWindowProperty(PROPERTY_INFO_ITEMS) or { }

    if 'query' not in params and ADDON.getSetting('cleanupEpisodes') == 'true':
        listItemFunc = makeListItemClean
    else:
        listItemFunc = makeListItem

    if params['section'] == 'ALL':
        sectionItems = chain.from_iterable(catalog[sectionName] for sectionName in sorted(catalog))
    else:
        sectionItems = catalog[params['section']]

    def _sectionItemsGen():
        if ADDON_LATEST_THUMBS and path == URL_PATHS['latest']:
            # Special-case for the 'Latest Releases' catalog, which has some thumbnails available.
            # Each 'entry' is (URL, htmlTitle, thumb).
            NO_THUMB = '-120-72.jpg' # As seen on 2019-04-15.
            for entry in sectionItems:
                entryURL = entry[0]
                entryArt = (
                    artDict if entry[2].startswith(NO_THUMB) else {'icon':ADDON_ICON,'thumb':entry[2],'poster':entry[2]}
                )
                # If there's metadata for this entry (requested by the user with "Show Information"), use it.
                if entryURL in infoItems:
                    itemPlot, itemThumb = infoItems[entryURL]
                    yield (
                        buildURL({'action': action, 'url': entryURL}),
                        listItemFunc(entry[1], entryURL, entryArt, itemPlot, isFolder, isSpecial, None),
                        isFolder
                    )
                else:
                    yield (
                        buildURL({'action': action, 'url': entryURL}),
                        listItemFunc(entry[1], entryURL, entryArt, '', isFolder, isSpecial, params),
                        isFolder
                    )
        else:
            # Normal item listing, each 'entry' is (URL, htmlTitle).
            for entry in sectionItems:
                entryURL = entry[0]
                if entryURL in infoItems:
                    itemPlot, itemThumb = infoItems[entryURL]
                    entryArt = {'icon': ADDON_ICON, 'thumb': itemThumb, 'poster': itemThumb, 'fanart': itemThumb}
                    yield (
                        buildURL({'action': action, 'url': entryURL}),
                        listItemFunc(entry[1], entryURL, entryArt, itemPlot, isFolder, isSpecial, None),
                        isFolder
                    )
                else:
                    yield (
                        buildURL({'action': action, 'url': entryURL}),
                        listItemFunc(entry[1], entryURL, artDict, '', isFolder, isSpecial, params),
                        isFolder
                    )

    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_sectionItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    setViewMode() # Set the skin layout mode, if the option is enabled.


def actionEpisodesMenu(params):
    xbmcplugin.setContent(PLUGIN_ID, 'episodes')

    # Memory-cache the last episode list, to help when the user goes back and forth while watching
    # multiple episodes of the same show. This way only one web request is needed for the same show.
    lastListURL = getRawWindowProperty(PROPERTY_EPISODE_LIST_URL)
    if lastListURL and lastListURL == params['url']:
        listData = getWindowProperty(PROPERTY_EPISODE_LIST_DATA)
    else:
        # New domain safety replace, in case the user is coming in from an old Kodi favorite item.
        if BASEURL == 'https://www.thewatchcartoononline.tv':
           url = params['url'].replace('user.wco.tv', 'www.thewatchcartoononline.tv', 1)
           r = requestHelper(url if url.startswith('http') else BASEURL + url)
           html = r.text
        else:
           url = params['url'].replace('www.thewatchcartoononline.tv', 'user.wco.tv', 1)
           r = requestHelper(url if url.startswith('http') else BASEURL + url)
           html = r.text

        plot, thumb = getPageMetadata(html)

        dataStartIndex = html.find('"sidebar_right3"')
        if dataStartIndex == -1:
            raise Exception('Episode list scrape fail: ' + url)

        # Episode list data: a tuple with the thumb, plot and an inner tuple of per-episode data.
        listData = (
            thumb,
            plot,
            tuple(
                match.groups()
                for match in re.finditer(
                    '''<a href="([^"]+).*?>([^<]+)''', html[dataStartIndex : html.find('"sidebar-all"')]
                )
            )
        )
        setRawWindowProperty(PROPERTY_EPISODE_LIST_URL, params['url'])
        setWindowProperty(PROPERTY_EPISODE_LIST_DATA, listData)

    def _episodeItemsGen():
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()

        showURL = params['url']
        thumb = listData[0]
        artDict = {'icon': thumb, 'thumb': thumb, 'poster': thumb, 'fanart': thumb} if thumb else None
        plot = listData[1]

        listItemFunc = makeListItemClean if ADDON.getSetting('cleanupEpisodes') == 'true' else makeListItem

        itemParams = {'action': 'actionResolve', 'url': None}
        listIter = iter(listData[2]) if ADDON.getSetting('reverseEpisodes') == 'true' else reversed(listData[2])
        for URL, title in listIter:
            item = listItemFunc(title, URL, artDict, plot, isFolder=False, isSpecial=False, oldParams=None)
            itemParams['url'] = URL
            itemURL = buildURL(itemParams)
            playlist.add(itemURL, item)
            yield (itemURL, item, False)

    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_episodeItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)


def actionLatestMoviesMenu(params):
    # Returns a list of links from a hidden "/anime/movies" area.
    # Since this page is very large (130 KB), we memory cache it after it's been requested.
    html = getRawWindowProperty(PROPERTY_LATEST_MOVIES)
    if not html:
        r = requestHelper(BASEURL + params['path'])
        html = r.text
        setRawWindowProperty(PROPERTY_LATEST_MOVIES, html)

    # Similar scraping logic to 'actionEpisodesMenu()'.

    dataStartIndex = html.find('"sidebar_right3"')
    if dataStartIndex == -1:
        raise Exception('Latest movies scrape fail: ' + url)

    # Persistent property with item metadata.
    infoItems = getWindowProperty(PROPERTY_INFO_ITEMS) or { }

    def _movieItemsGen():
        artDict = {'icon': ADDON_ICON, 'thumb': ADDON_ICON, 'poster': ADDON_ICON, 'fanart': ADDON_FANART}
        reIter = re.finditer(
            '''<a href="([^"]+).*?>([^<]+)''', html[dataStartIndex : html.find('"sidebar-all"')]
        )
        # The page has like 6000 items going back to 2010, so we limit to only the latest 200.
        for x in range(200):
            entryURL, entryTitle = next(reIter).groups()
            if entryURL in infoItems:
                entryPlot, entryThumb = infoItems[entryURL]
                yield (
                    buildURL({'action': 'actionResolve', 'url': entryURL}),
                    makeListItem(
                        unescapeHTMLText(entryTitle),
                        entryURL,
                        {'icon': ADDON_ICON, 'thumb': entryThumb, 'poster': entryThumb, 'fanart': ADDON_FANART},
                        entryPlot,
                        isFolder = False,
                        isSpecial = True,
                        oldParams = None
                    ),
                    False
                )
            else:
                yield (
                    buildURL({'action': 'actionResolve', 'url': entryURL}),
                    makeListItem(
                        unescapeHTMLText(entryTitle),
                        entryURL,
                        artDict,
                        '',
                        isFolder = False,
                        isSpecial = True,
                        oldParams = params
                    ),
                    False
                )
    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_movieItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    setViewMode()


# A sub menu, lists search options.
def actionSearchMenu(params):
    def _modalKeyboard(heading):
        kb = xbmc.Keyboard('', heading)
        kb.doModal()
        return kb.getText() if kb.isConfirmed() else ''

    if 'searchType' in params:
        # Support for the 'actionShowInfo()' function reloading this route, sending it an already searched query.
        # This also supports external query calls, like from OpenMeta.
        if 'query' in params:
            query = params['query']
        else:
            query = _modalKeyboard(params.get('searchTitle', 'Search'))

        if query:
            historyTypeIDs = {'series':'0', 'movies':'1', 'episodes':'2'}
            previousHistory = ADDON.getSetting('searchHistory')
            if previousHistory:
                # Limit search history to 40 items.
                if previousHistory.count('\n') == 40:
                    previousHistory = previousHistory[:previousHistory.rfind('\n')] # Forget the oldest search result.
                ADDON.setSetting('searchHistory', historyTypeIDs[params['searchType']] + query + '\n' + previousHistory)
            else:
                ADDON.setSetting('searchHistory', historyTypeIDs[params['searchType']] + query)

            params['query'] = query
            params['section'] = 'ALL' # Force an uncategorized display (results are usually few).
            actionCatalogSection(params) # Send the search type and query for the catalog functions to use.
        return

    xbmcplugin.addDirectoryItems(
        PLUGIN_ID,
        (
            (
                buildURL({
                    'action': 'actionSearchMenu',
                    'path': URL_PATHS['search'], # A special, non-web path used by 'getCatalogProperty()'.
                    'searchType': 'series',
                    'searchTitle': 'Search Cartoon/Anime Name'
                }),
                xbmcgui.ListItem('[COLOR lavender][B]Search Cartoon/Anime Name[/B][/COLOR]'),
                True
            ),
            (
                buildURL({
                    'action': 'actionSearchMenu',
                    'path': URL_PATHS['search'],
                    'searchType': 'movies',
                    'searchTitle': 'Search Movie Name'
                }),
                xbmcgui.ListItem('[COLOR lavender][B]Search Movie Name[/B][/COLOR]'),
                True
            ),
            (
                buildURL({
                    'action': 'actionSearchMenu',
                    'path': URL_PATHS['search'],
                    'searchType': 'episodes',
                    'searchTitle': 'Search Episode Name'
                }),
                xbmcgui.ListItem('[COLOR lavender][B]Search Episode Name[/B][/COLOR]'),
                True
            ),
            (
                buildURL({'action': 'actionGenresMenu', 'path': URL_PATHS['genre']}),
                xbmcgui.ListItem('[COLOR lavender][B]Search by Genre[/B][/COLOR]'),
                True
            ),
            (
                buildURL({'action': 'actionTraktMenu', 'path': 'trakt'}),
                xbmcgui.ListItem('[COLOR lavender][B]Search by Trakt List[/B][/COLOR]'),
                True
            ),
            (
                buildURL({'action': 'actionSearchHistory', 'path': 'searchHistory'}),
                xbmcgui.ListItem('[COLOR lavender][B]Search History...[/B][/COLOR]'),
                True
            )
        )
    )
    xbmcplugin.endOfDirectory(PLUGIN_ID)


# A sub menu, lists all previous searches along with their categories.
def actionSearchHistory(params):
    history = ADDON.getSetting('searchHistory').split('\n') # Non-UI setting, it's just a big string.

    # A blank string split creates a list with a blank string inside, so test if the first item is valid.
    if history[0]:
        # Use list indexes to map to 'searchType' and a label prefix.
        historyTypeNames = ['series', 'movies', 'episodes']
        historyPrefixes = ['(Cartoon/Anime)', '(Movie)', '(Episode)']

        searchPath = URL_PATHS['search']

        historyItems = tuple(
            (
                buildURL({
                    'query': itemQuery,
                    'searchType': historyTypeNames[itemType],
                    'path': searchPath,
                    'section': 'ALL',
                    'action': 'actionCatalogSection'
                }),
                xbmcgui.ListItem('[B]%s[/B] "%s"' % (historyPrefixes[itemType], itemQuery)),
                True
            )
            for itemType, itemQuery in (
                (int(itemString[0]), itemString[1:]) for itemString in history
            )
        )
        clearHistoryItem = (
            buildURL({'action': 'actionSearchHistoryClear'}), xbmcgui.ListItem('[B]Clear History...[/B]'), False
        )
        xbmcplugin.addDirectoryItems(PLUGIN_ID, (clearHistoryItem,) + historyItems)
    else:
        xbmcplugin.addDirectoryItem(PLUGIN_ID, '', xbmcgui.ListItem('(No History)'), isFolder=False)
    xbmcplugin.endOfDirectory(PLUGIN_ID)


def actionSearchHistoryClear(params):
    dialog = xbmcgui.Dialog()
    if dialog.yesno('Clear Search History', 'Are you sure?'):
        ADDON.setSetting('searchHistory', '')
        dialog.notification('WatchNixtoons2', 'Search history cleared', xbmcgui.NOTIFICATION_INFO, 3000, False)
        # Show the search menu afterwards.
        xbmc.executebuiltin('Container.Update(' + PLUGIN_URL + '?action=actionSearchMenu,replace)')


# A sub menu, lists the genre categories in the genre search.
def actionGenresMenu(params):
    r = requestHelper(BASEURL + URL_PATHS['genre'])
    html = r.text

    dataStartIndex = html.find(r'ddmcc">')
    if dataStartIndex == -1:
        raise Exception('Genres list scrape fail')

    xbmcplugin.addDirectoryItems(
        PLUGIN_ID,
        tuple(
            (
                buildURL(
                    {
                        'action': 'actionCatalogMenu',
                        'path': '/search-by-genre/' + match.group(1).rsplit('/', 1)[1],
                        'searchType': 'genres'
                    }
                ),
                xbmcgui.ListItem(match.group(2)),
                True
            )
            for match in re.finditer('''<a.*?"([^"]+).*?>(.*?)</''', html[dataStartIndex : html.find(r'</div></div>')])
        )
    )
    xbmcplugin.endOfDirectory(PLUGIN_ID)


def actionTraktMenu(params):
    instance = SimpleTrakt.getInstance()
    if instance.ensureAuthorized(ADDON):

        def _traktMenuItemsGen():
            traktIconDict = {'icon': ADDON_TRAKT_ICON, 'thumb': ADDON_TRAKT_ICON, 'poster': ADDON_TRAKT_ICON}
            for listName, listURL, listDescription in instance.getUserLists(ADDON):
                item = xbmcgui.ListItem(listName)
                item.setArt(traktIconDict)
                item.setInfo('video', {'title': listName, 'plot': listDescription})
                yield (
                    buildURL({'action': 'actionTraktList', 'listURL': listURL}),
                    item,
                    True
                )

        xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_traktMenuItemsGen()))
        xbmcplugin.endOfDirectory(PLUGIN_ID) # Only finish the directory if the user is authorized it.


def actionTraktList(params):
    instance = SimpleTrakt.getInstance()
    if instance.ensureAuthorized(ADDON):

        def _traktListItemsGen():
            traktIconDict = {'icon': ADDON_TRAKT_ICON, 'thumb': ADDON_TRAKT_ICON, 'poster': ADDON_TRAKT_ICON}
            for itemName, overview, searchType, query in sorted(instance.getListItems(params['listURL'], ADDON)):
                item = xbmcgui.ListItem(itemName)
                item.setInfo('video', {'title': itemName, 'plot': overview})
                item.setArt(traktIconDict)
                yield (
                    # Trakt items will lead straight to a show name search.
                    buildURL(
                        {
                            'action': 'actionCatalogMenu',
                            'path': URL_PATHS['search'],
                            'query': query,
                            'searchType': searchType,
                        }
                    ),
                    item,
                    True
                )

        xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_traktListItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)


def actionTraktAbout(params):
    xbmcgui.Dialog().ok(
        'WatchNixtoons2',
        'To search for items in your Trakt lists in WNT2, go to [B]Search > Search by Trakt List[/B] and pair your ' \
        'account. Searching for an item this way does a name search, same as if you went and searched for that ' \
        'name manually.'
    )


def actionClearTrakt(params):
    if 'watchnixtoons2' in xbmc.getInfoLabel('Container.PluginName'):
        xbmc.executebuiltin('Dialog.Close(all)')

    # Kinda buggy behavior.
    # Need to wait a bit and recreate the xbmcaddon.Addon() reference, otherwise the settings
    # don't seem to be changed.
    # See https://forum.kodi.tv/showthread.php?tid=290353&pid=2425543#pid2425543
    global ADDON
    xbmc.sleep(500)
    if SimpleTrakt.clearTokens(ADDON):
        xbmcgui.Dialog().notification('WatchNixtoons2', 'Trakt tokens cleared', xbmcgui.NOTIFICATION_INFO, 3500, False)
    else:
        xbmcgui.Dialog().notification(
            'WatchNixtoons2', 'Trakt tokens already cleared', xbmcgui.NOTIFICATION_INFO, 3500, False
        )
    ADDON = xbmcaddon.Addon()


def actionRestoreDatabase(params):
    if not xbmcgui.Dialog().yesno(
        'WatchNixtoons2',
        'This will update the Kodi database to remember any WatchNixtoons2 episodes that were already watched, ' \
        'but forgotten after an add-on update.\nProceed?',
        nolabel = 'Cancel',
        yeslabel = 'Ok'
    ):
        return

    # Action called from the settings dialog.
    # This will update all the WatchNixtoons2 'strFilename' columns of table 'files' of Kodi's MyVideos###.db
    # with the new BASEURL used by the add-on so that episodes are still considered as watched (playcount >= 1).

    import xbmcvfs
    try:
        import sqlite3
    except:
        xbmcgui.Dialog().notification(
            'WatchNixtoons2', 'sqlite3 not found', xbmcgui.NOTIFICATION_WARNING, 3000, True
        )
        return

    # Find the 'MyVideos###.db' file.
    dirs, files = xbmcvfs.listdir('special://database')
    for file in files:
        if 'MyVideos' in file and file.endswith('.db'):
            path = xbmc.translatePath('special://database/' + file)
            break
    else:
        xbmcgui.Dialog().notification(
            'WatchNixtoons2', 'MyVideos database file not found', xbmcgui.NOTIFICATION_WARNING, 3000, True
        )
        return

    # Update the database.

    OLD_DOMAINS = getOldDomains()
    NEW_DOMAIN = BASEURL.replace('https://', '', 1) # Make sure to strip the scheme from the current address.
    replaceDomainFunc = lambda original, oldDomain: original.replace(oldDomain, NEW_DOMAIN)
    totalUpdates = 0

    try:
        connection = sqlite3.connect(path)
    except Exception as e:
        xbmcDebug(e)
        xbmcgui.Dialog().notification(
            'WatchNixtoons2', 'Unable to connect to MyVideos database', xbmcgui.NOTIFICATION_WARNING, 3000, True
        )
        return

    getCursor = connection.cursor()
    setCursor = connection.cursor()
    pattern = 'plugin://plugin.video.watchnixtoons2/%actionResolve%'
    for idFile, strFilename in getCursor.execute(
        "SELECT idFile,strFilename FROM files WHERE strFilename LIKE '%s'" % pattern
    ):
        if any(oldDomain in strFilename for oldDomain in OLD_DOMAINS):
            strFilename = reduce(replaceDomainFunc, OLD_DOMAINS, strFilename)
            setCursor.execute("UPDATE files SET strFilename=? WHERE idFile=?", (strFilename, idFile))
            totalUpdates += 1

    try:
        if totalUpdates:
            connection.commit() # Only commit if needed.
        connection.close()
    except:
        xbmcgui.Dialog().notification(
            'WatchNixtoons2',
            'Unable to update the database (file permission error?)',
            xbmcgui.NOTIFICATION_WARNING,
            3000,
            True
        )
        return

    # Bring a notification before finishing.
    if totalUpdates:
        xbmcgui.Dialog().ok('WatchNixtoons2', 'Database update complete (%i items updated).' % totalUpdates)
    else:
        xbmcgui.Dialog().ok('WatchNixtoons2', 'Finished. No updates needed (0 items updated).')


def actionUpdateFavourites(params):
    if not xbmcgui.Dialog().yesno(
        'WatchNixtoons2',
        'This will update any of your Kodi Favourites created with older versions of WatchNixtoons2 so they can point ' \
        'to the latest web address that the add-on uses.\nProceed?',
        nolabel = 'Cancel',
        yeslabel = 'Ok'
    ):
        return

    # Action called from the settings dialog.
    # This will update all the Kodi favourites that use WatchNixtoons2 so that they use the new BASEURL.

    import xbmcvfs
    FAVOURITES_PATH = 'special://userdata/favourites.xml'

    file = xbmcvfs.File(FAVOURITES_PATH)
    favoritesText = file.read()
    file.close()
    originalText = favoritesText[:] # Get a backup copy of the content.

    OLD_DOMAINS = getOldDomains()
    NEW_DOMAIN = BASEURL.replace('https://', '', 1) # Make sure to strip the scheme.
    replaceDomainFunc = lambda original, oldDomain: original.replace(oldDomain, NEW_DOMAIN)

    if any(oldDomain in originalText for oldDomain in OLD_DOMAINS):
        favoritesText = reduce(replaceDomainFunc, getOldDomains(), favoritesText)
        try:
            file = xbmcvfs.File(FAVOURITES_PATH, 'w')
            file.write(favoritesText)
            file.close()
        except:
            try:
                # Try again, in case this was some weird encoding error and not a write-permission error.
                file = xbmcvfs.File(FAVOURITES_PATH, 'w')
                file.write(originalText)
                file.close()
                detail = ' (original was restored)'
            except:
                detail = ''

            xbmcgui.Dialog().notification(
                'WatchNixtoons2', 'Error while writing to file' + detail, xbmcgui.NOTIFICATION_WARNING, 3000, True
            )
            return

        if 'watchnixtoons2' in xbmc.getInfoLabel('Container.PluginName'):
            xbmc.executebuiltin('Dialog.Close(all)')

        xbmcgui.Dialog().ok(
            'WatchNixtoons2', 'One or more items updated succesfully. Kodi will now reload the Favourites file...'
        )
        xbmc.executebuiltin('LoadProfile(%s)' % xbmc.getInfoLabel('System.ProfileName')) # Reloads 'favourites.xml'.
    else:
        xbmcgui.Dialog().ok('WatchNixtoons2', 'Finished. No old favorites found.')

#Added by Christian Haitian
def actionClearCookies(params):
    if not xbmcgui.Dialog().yesno(
        'WatchNixtoons2',
        'This will clear the stored cookies for WatchNixToons2 Premimum site.  Do this if you entered  ' \
        'wrong credentials and attempted to use the plugin or recently changed your credentials.\nProceed?',
        nolabel = 'Cancel',
        yeslabel = 'Ok'
    ):
        return

    # Action called from the settings dialog.
    # Clear stored cookie file from addon folder.

    os.remove(cookieFile)
    xbmcgui.Dialog().ok('WatchNixtoons2', 'Successfully cleared cookies.')

def actionShowSettings(params):
    # Modal dialog, so the program won't continue from this point until user closes\confirms it.
    ADDON.openSettings()

    # So right after it is a good time to update any settings globals.

    global ADDON_SHOW_CATALOG
    ADDON_SHOW_CATALOG = ADDON.getSetting('showCatalog') == 'true'

    global ADDON_LATEST_DATE
    # Set the catalog to be reloaded in case the user changed the "Order 'Latest Releases' By Date" setting.
    newLatestDate = ADDON.getSetting('useLatestDate') == 'true'
    if ADDON_LATEST_DATE != newLatestDate and URL_PATHS['latest'] in getRawWindowProperty(PROPERTY_CATALOG_PATH):
        setRawWindowProperty(PROPERTY_CATALOG_PATH, '')
    ADDON_LATEST_DATE = newLatestDate

    global ADDON_LATEST_THUMBS
    ADDON_LATEST_THUMBS = ADDON.getSetting('showLatestThumbs') == 'true'


def getPageMetadata(html):
    # If we're on an episode or (old) movie page, see if there's a parent page with the actual metadata.
    stringStartIndex = html.find('"header-tag"')
    if stringStartIndex != -1:
        parentURL = re.search('href="([^"]+)', html[stringStartIndex:]).group(1)
        if '/anime/movies' not in parentURL:
            r = requestHelper(parentURL if parentURL.startswith('http') else BASEURL + parentURL)
            if r.ok:
                html = r.text

    # Thumbnail scraping.
    thumb = ''
    stringStartIndex = html.find('og:image" content="')
    if stringStartIndex != -1:
        thumbPath = html[stringStartIndex+19 : html.find('"', stringStartIndex+19)] # 19 = len('og:image" content="')
        if thumbPath:
            if thumbPath.startswith('http'):
                thumb = thumbPath + getThumbnailHeaders()
            elif thumbPath.startswith('/'):
                thumb = BASEURL + thumbPath + getThumbnailHeaders()

    # (Show) plot scraping.
    plot = ''
    stringStartIndex = html.find('Info:')
    if stringStartIndex != -1:
        match = re.search('</h3>\s*<p>(.*?)</p>', html[stringStartIndex:], re.DOTALL)
        plot = unescapeHTMLText(match.group(1).strip()) if match else ''

    return plot, thumb


def actionShowInfo(params):
    xbmcgui.Dialog().notification('WatchNixtoons2', 'Requesting info...', ADDON_ICON, 2000, False)

    # Get the desktop page for the item, whatever it is.
    url = params['url'].replace('/m.', '/www.', 1) # Make sure the URL points to the desktop site.
    r = requestHelper(url if url.startswith('http') else BASEURL + url)
    html = r.text

    plot, thumb = getPageMetadata(html)

    # Use a persistent memory property holding a dictionary, and refresh the directory listing.
    if plot or thumb:
        infoItems = getWindowProperty(PROPERTY_INFO_ITEMS) or { }
        infoItems[url] = (plot, (thumb or 'DefaultVideo.png'))
        setWindowProperty(PROPERTY_INFO_ITEMS, infoItems)
        oldParams = dict(parse_qsl(params['oldParams']))
        xbmc.executebuiltin('Container.Update(%s,replace)' % (PLUGIN_URL + '?' + params['oldParams']))
    else:
        xbmcgui.Dialog().notification('WatchNixtoons2', 'No info found', ADDON_ICON, 1500, False)


def unescapeHTMLText(text):
    text = text.encode('utf-8') if isinstance(text, str) else str(text, errors='ignore').encode('utf-8')
    # Unescape HTML entities.
    if r'&#' in text:
        # Strings found by regex-searching on all lists in the source website. It's very likely to only be these.
        return text.replace(r'&#8216;', 'â€˜').replace(r'&#8221;', 'â€').replace(r'&#8211;', 'â€“').replace(r'&#038;', '&')\
        .replace(r'&#8217;', 'â€™').replace(r'&#8220;', 'â€œ').replace(r'&#8230;', 'â€¦').replace(r'&#160;', ' ')\
        .replace(r'&amp;', '&')
    else:
        return text.replace(r'&amp;', '&')


def getTitleInfo(unescapedTitle):
    # We need to interpret the full title of each episode's link's string
    # for information like episode number, season and show title.
    season = None
    episode = None
    multiPart = None
    showTitle = unescapedTitle
    episodeTitle = ''

    seasonIndex = unescapedTitle.find('Season ') # 7 characters long.
    if seasonIndex != -1:
        season = unescapedTitle[seasonIndex+7 : unescapedTitle.find(' ', seasonIndex+7)]
        if not season.isdigit():
            # Handle inconsistently formatted episode title, with possibly ordinal season before or after
            # the word "Season" (case unknown, inconsistent).
            if season == 'Episode':
                # Find the word to the left of "Season ", separated by spaces (spaces not included in the result).
                season = unescapedTitle[unescapedTitle.rfind(' ', 0, seasonIndex-1) + 1 : seasonIndex-1]
                showTitle = unescapedTitle[:seasonIndex+7].strip(' -â€“:') # Include the "nth Season" term in the title.
            else:
                showTitle = unescapedTitle[:seasonIndex].strip(' -â€“:')
            season = {'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5'}.get(season.lower(), '')
        else:
            showTitle = unescapedTitle[:seasonIndex].strip(' -â€“:')

    episodeIndex = unescapedTitle.find(' Episode ') # 9 characters long.
    if episodeIndex != -1:
        spaceIndex = unescapedTitle.find(' ', episodeIndex+9)
        if spaceIndex > episodeIndex:
            episodeSplit = unescapedTitle[episodeIndex+9 : spaceIndex].split('-') # For multipart episodes, like "42-43".
            episode = list(filter(str.isdigit, episodeSplit[0]))
            multiPart = list(filter(str.isdigit, episodeSplit[1])) if len(episodeSplit) > 1 else None

            # Get the episode title string (stripped of spaces, hyphens and en-dashes).
            englishIndex = unescapedTitle.rfind(' English', spaceIndex)
            if englishIndex != -1:
                episodeTitle = unescapedTitle[spaceIndex+1 : englishIndex].strip(' -â€“:')
            else:
                episodeTitle = unescapedTitle[spaceIndex+1:].strip(' -â€“:')
            # Safeguard for when season 1 is ocasionally omitted in the title.
            if not season:
                season = '1'

    if episode:
        return (showTitle[:episodeIndex].strip(' -'), season, episode, multiPart, episodeTitle.strip(' /'))
    else:
        englishIndex = unescapedTitle.rfind(' English')
        if englishIndex != -1:
            return (unescapedTitle[:englishIndex].strip(' -'), None, None, None, '')
        else:
            return (unescapedTitle.strip(' -'), None, None, None, '')


def makeListItem(title, url, artDict, plot, isFolder, isSpecial, oldParams):
    unescapedTitle = unescapeHTMLText(title)
    item = xbmcgui.ListItem(unescapedTitle)
    isPlayable = False

    if not (isFolder or isSpecial):
        title, season, episode, multiPart, episodeTitle = getTitleInfo(unescapedTitle)
        # Playable content.
        isPlayable = True
        itemInfo = {
            'mediatype': 'episode' if episode else 'tvshow', 'tvshowtitle': title, 'title': episodeTitle, 'plot': plot
        }
        if episode and episode.isdigit():
            itemInfo['season'] = int(season) if season.isdigit() else -1
            itemInfo['episode'] = int(episode)
        item.setInfo('video', itemInfo)
    elif isSpecial:
        isPlayable = True
        item.setInfo('video', {'mediatype': 'movie', 'title': unescapedTitle, 'plot': plot})
    else:
        item.setInfo('video', {'mediatype': 'tvshow', 'title': unescapedTitle, 'plot': plot})

    if artDict:
        item.setArt(artDict)

    # Add the context menu items, if necessary.
    contextMenuList = None
    if oldParams:
        contextMenuList = [
            (
                'Nixtoons Information',
                'RunPlugin('+PLUGIN_URL+'?action=actionShowInfo&url='+quote_plus(url)+'&oldParams='+quote_plus(urlencode(oldParams))+')'
            )
        ]
    if isPlayable:
        item.setProperty('IsPlayable', 'true') # Allows the checkmark to be placed on watched episodes.
        playChaptersItem = (
            'Play Chapters',
            'PlayMedia('+PLUGIN_URL+'?action=actionResolve&url='+quote_plus(url)+'&playChapters=1)'
        )
        if contextMenuList:
            contextMenuList.append(playChaptersItem)
        else:
            contextMenuList = [playChaptersItem]
    if contextMenuList:
        item.addContextMenuItems(contextMenuList)

    return item


# Variant of the 'makeListItem()' function that tries to format the item label using the season and episode.
def makeListItemClean(title, url, artDict, plot, isFolder, isSpecial, oldParams):
    unescapedTitle = unescapeHTMLText(title)
    isPlayable = False

    if isFolder or isSpecial:
        item = xbmcgui.ListItem(unescapedTitle)
        if isSpecial:
            isPlayable = True
            item.setInfo('video', {'mediatype': 'video', 'title': unescapedTitle})
    else:
        title, season, episode, multiPart, episodeTitle = getTitleInfo(unescapedTitle)
        if episode and episode.isdigit():
            # The clean episode label will have this format: "SxEE Episode Name", with S and EE standing for digits.
            item = xbmcgui.ListItem(
                '[B]' + season + 'x' + episode.zfill(2) + ('-' + multiPart if multiPart else '') + '[/B] '
                + (episodeTitle or title)
            )
            itemInfo = {
                'mediatype': 'episode',
                'tvshowtitle': title,
                'title': title,
                'plot': plot,
                'season': int(season) if season.isdigit() else -1,
                'episode': int(episode)
            }
        else:
            item = xbmcgui.ListItem(title)
            itemInfo = {'mediatype': 'tvshow', 'tvshowtitle': title, 'title': title, 'plot': plot}
        item.setInfo('video', itemInfo)
        isPlayable = True

    if artDict:
        item.setArt(artDict)

    # Add the context menu items, if necessary.
    contextMenuList = None
    if oldParams:
        contextMenuList = [
            (
                'Show Information',
                'RunPlugin('+PLUGIN_URL+'?action=actionShowInfo&url='+quote_plus(url)+'&oldParams='+quote_plus(urlencode(oldParams))+')'
            )
        ]
    if isPlayable:
        item.setProperty('IsPlayable', 'true') # Allows the checkmark to be placed on watched episodes.
        playChaptersItem = (
            'Play Chapters',
            'PlayMedia('+PLUGIN_URL+'?action=actionResolve&url='+quote_plus(url)+'&playChapters=1)'
        )
        if contextMenuList:
            contextMenuList.append(playChaptersItem)
        else:
            contextMenuList = [playChaptersItem]
    if contextMenuList:
        item.addContextMenuItems(contextMenuList)

    return item


'''
(1. The catalog is a dictionary of lists, used to store data between add-on states to make xbmcgui.ListItems:
{
    (2. Sections, as in alphabet sections of items, A, B, C, D, E, F etc., each section holds a list of items.)
    A: (
        (item, item, item, ...) (3. Items, each item is a pair of <a> properties: (a.string, a['href']).)
    )
    B: (...)
    C: (...)
}
'''

# Manually sorts items from an iterable into an alphabetised catalog.
# Iterable contains (URL, name) pairs that might refer to a series, episode, ova or movie.
def catalogFromIterable(iterable):
    catalog = {key: [ ] for key in ascii_uppercase}
    miscSection = catalog['#'] = [ ]
    for item in iterable:
        key = item[1][0].upper()
        if key in catalog:
            catalog[key].append(item)
        else:
            miscSection.append(item)
    return catalog


def makeLatestCatalog(params):
    # Returns a list of links from the "Latest 50 Releases" area, but from their mobile site as it has lots of items.
    r = requestHelper(BASEURL_MOBILE) # Path unused, data is already on the homepage.
    html = r.text

    dataStartIndex = html.find('vList')
    if dataStartIndex == -1:
        raise Exception('(Mobile) Latest catalog scrape fail')

    thumbHeaders = getThumbnailHeaders()

    if ADDON_LATEST_DATE:
        # Make the catalog dict only have a single section, "LATEST", with items listed as they are.
        # This way the actionCatalogMenu() function will show this single section directly, with no alphabet categories.
        return {
            'LATEST': tuple(
                (match.group(1), match.group(3), BASEURL_MOBILE + match.group(2) + thumbHeaders)
                for match in re.finditer(
                    '''<a href="([^"]+).*?img src="([^"]+).*?div.*?div>(.*?)</div''', html[dataStartIndex : html.find('/ol')]
                )
            )
        }
    else:
        return catalogFromIterable(
            (match.group(1), match.group(3), BASEURL_MOBILE + match.group(2) + thumbHeaders)
            for match in re.finditer(
                '''<a href="([^"]+).*?img src="([^"]+).*?div.*?div>(.*?)</div''', html[dataStartIndex : html.find('/ol')]
            )
        )


def makePopularCatalog(params):
    r = requestHelper(BASEURL) # We will scrape from the sidebar content on the homepage.
    html = r.text

    dataStartIndex = html.find('"sidebar-titles"')
    if dataStartIndex == -1:
        raise Exception('Popular catalog scrape fail: ' + params['path'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            '''<a href="([^"]+).*?>([^<]+)''', html[dataStartIndex : html.find('</div>', dataStartIndex)]
        )
    )


def makeSeriesSearchCatalog(params):
    r = requestHelper(
        BASEURL+'/search', data={'catara': params['query'], 'konuara': 'series'}, extraHeaders={'Referer': BASEURL+'/'})
    html = r.text

    dataStartIndex = html.find('submit')
    if dataStartIndex == -1:
        raise Exception('Series search scrape fail: ' + params['query'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            '''<a href="([^"]+)[^>]*>([^<]+)</a''',
            html[dataStartIndex : html.find('cizgiyazisi', dataStartIndex)]
        )
    )


def makeMoviesSearchCatalog(params):
    # Try a movie category search (same code as in 'makeGenericCatalog()').
    r = requestHelper(BASEURL + URL_PATHS['movies'])
    html = r.text

    dataStartIndex = html.find('"ddmcc"')
    if dataStartIndex == -1:
        raise Exception('Movies search scrape fail: ' + params['query'])

    lowerQuery = params['query'].lower()

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            '''<a href="([^"]+).*?>([^<]+)''', html[dataStartIndex : html.find('/ul></ul', dataStartIndex)]
        )
        if lowerQuery in match.group(2).lower()
    )


def makeEpisodesSearchCatalog(params):
    r = requestHelper(
        BASEURL+'/search', data={'catara': params['query'], 'konuara': 'episodes'}, extraHeaders={'Referer': BASEURL+'/'}
    )
    html = r.text

    dataStartIndex = html.find('submit')
    if dataStartIndex == -1:
        raise Exception('Episode search scrape fail: ' + params['query'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            '''<a href="([^"]+)[^>]*>([^<]+)</a''',
            html[dataStartIndex : html.find('cizgiyazisi', dataStartIndex)],
            re.DOTALL
        )
    )


def makeSearchCatalog(params):
    searchType = params.get('searchType', 'series')
    if searchType == 'series':
        return makeSeriesSearchCatalog(params)
    elif searchType == 'movies':
        return makeMoviesSearchCatalog(params)
    else:
        return makeEpisodesSearchCatalog(params)


def makeGenericCatalog(params):
    # The movies path is missing some items when scraped from BASEURL_MOBILE, so we use the BASEURL
    # (full website) in here.
    r = requestHelper(BASEURL + params['path'])
    html = r.text

    dataStartIndex = html.find('"ddmcc"')
    if dataStartIndex == -1:
        raise Exception('Generic catalog scrape fail: ' + params['path'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            '''<li><a href="([^"]+).*?>([^<]+)''', html[dataStartIndex : html.find('</div>', dataStartIndex)]
        )
    )


# Retrieves the catalog from a persistent XBMC window property between different add-on
# directories, or recreates the catalog based on one of the catalog functions.
def getCatalogProperty(params):
    path = params['path']

    def _rebuildCatalog():
        func = CATALOG_FUNCS.get(path, makeGenericCatalog)
        catalog = func(params)
        setWindowProperty(PROPERTY_CATALOG, catalog)
        if 'query' in params:
            # For searches, store the query and search type in the catalog path so we can identify
            # this particular search attempt.
            setRawWindowProperty(PROPERTY_CATALOG_PATH, path + params['query'] + params['searchType'])
        else:
            setRawWindowProperty(PROPERTY_CATALOG_PATH, path)
        setRawWindowProperty(PROPERTY_INFO_ITEMS, '') # Clear any previous info.
        return catalog

    # If these properties are empty (like when coming in from a favourites menu), or if
    # a different catalog (a different URL path) is stored in this property, then reload it.
    currentPath = getRawWindowProperty(PROPERTY_CATALOG_PATH)
    if (
        # "If we're coming in from a search and the search query and type are different, or if we're not
        # coming in from a search and the paths are simply different, rebuild the catalog."
        ('query' in params and (params['query'] not in currentPath or params['searchType'] not in currentPath))
        or ('query' not in params and currentPath != path)
    ):
        catalog = _rebuildCatalog()
    else:
        catalog = getWindowProperty(PROPERTY_CATALOG)
        if not catalog:
            catalog = _rebuildCatalog()
    return catalog


def actionResolve(params):
#Mod by Christian Haitian starts here
   if BASEURL == 'https://user.wco.tv':
    # Needs to be the BASEURL domain to get multiple video qualities.
    url = params['url']
    # Sanitize the URL since on some occasions it's a path instead of full address.
    url = url if url.startswith('http') else (BASEURL + (url if url.startswith('/') else '/' + url))
    r = requestHelper(url.replace('watchcartoononline.io', 'user.wco.tv', 1)) # New domain safety.
    content = r.content

    def _decodeSource(subContent):
        # All links in premium site seem to start with file, we'll search for those in the content
        demlinks = re.findall(r" src: '(.*?)'",str(subContent))

        try:
            return demlinks

        except:
            return None # Probably a temporary block, or change in embedded code.

#    premiumlinks = re.findall(r'file: "(.*?)"',str(content))

    embedURL = None

    embedURLPattern = b'onclick="myFunction'
    embedURLIndex = content.find(embedURLPattern)
    if 'playChapters' in params or ADDON.getSetting('chapterEpisodes') == 'true':
        # Multi-chapter episode found (that is, multiple embedURLPattern statements found).
        # Extract all chapters from the page.
        embedURLPatternLen = len(embedURLPattern)
        currentPlayerIndex = embedURLIndex
        dataIndices = [ ]
        while currentPlayerIndex != -1:
            dataIndices.append(currentPlayerIndex)
            currentPlayerIndex = content.find(embedURLPattern, currentPlayerIndex + embedURLPatternLen)

        # If more than one "embedURL" statement found, make a selection dialog and call them "chapters".
        if len(dataIndices) > 1:
            selectedIndex = xbmcgui.Dialog().select(
                'Select Chapter', ['Chapter '+str(n) for n in range(1, len(dataIndices)+1)]
            )
        else:
            selectedIndex = 0

        if selectedIndex == 0:
         embedURL = re.findall(r'file: "(.*?)"',str(content))  
        elif selectedIndex != -1:
         embedURL = _decodeSource(content[dataIndices[selectedIndex]:])
        else:
            return # User cancelled the chapter selection.
    else:
        # Normal / single-chapter episode.
        embedURL = re.findall(r'file: "(.*?)"',str(content))  
        # User asked to play multiple chapters, but only one chapter/video player found.
        if embedURL and 'playChapters' in params:
            xbmcgui.Dialog().notification('WatchNixtoons2', 'Only 1 chapter found...', ADDON_ICON, 2000, False)

    premiumlinks = embedURL
    mediaURL = None

    if len(premiumlinks) == 1: # Only one quality available.
        mediaURL = premiumlinks[0]
    elif len(premiumlinks) > 0:
        # Allows user to select a prefered quality and double checks if the link is live.  If not, use the other link instead
        try:
            premiumlinks0 = requests.head(str(premiumlinks[0]), timeout=10, allow_redirects=True)
        except requests.exceptions.RequestException as error:
            premiumlinks0 = error
        try:
            premiumlinks1 = requests.head(str(premiumlinks[1]), timeout=10, allow_redirects=True)
        except requests.exceptions.RequestException as error:
            premiumlinks1 = error

        playbackMethod = ADDON.getSetting('playbackMethod')
        if playbackMethod == '0': # Select quality.
                selectedIndex = xbmcgui.Dialog().select(
                    'Select Quality', ['SD', 'HD']
                )
                if selectedIndex == 0:
                    mediaURL = premiumlinks[0] if premiumlinks0 == 'Response [200]' and re.search(r'.720p.',str(premiumlinks[0])) == None else premiumlinks[1]
                elif selectedIndex == -1:
                    mediaURL = None
                else:
                    mediaURL = premiumlinks[1] if premiumlinks1 == 'Response [200]' and re.search(r'.720p.',str(premiumlinks[1])) != None else premiumlinks[0]
        else: # Auto-play user choice.
            if playbackMethod == '1':
             mediaURL = premiumlinks[1] if str(premiumlinks1) == '<Response [200]>' and re.search(r'.720p.',str(premiumlinks[1])) != None else premiumlinks[0]
            else:
             mediaURL = premiumlinks[0] if str(premiumlinks0) == '<Response [200]>' and re.search(r'.720p.',str(premiumlinks[0])) == None else premiumlinks[1]

    else: #Check free site in case of a new release that's not on the premium site yet.
     xbmcgui.Dialog().notification('Trying free stream', '')
     r = requestHelper(url.replace('user.wco.tv', 'www.thewatchcartoononline.tv', 1)) # Change from premium site to free site
     content = r.content

     def _decodeSource(subContent):
        chars = subContent[subContent.find('[') : subContent.find(']')]
        spread = int(re.search(r' - (\d+)\)\; }', subContent[subContent.find(' - '):]).group(1))
        iframe = ''.join(
            chr(
                int(''.join(c for c in b64decode(char) if c.isdigit())) - spread
            )
            for char in chars.replace('"', '').split(',')
        )
        try:
            return BASEURL + re.search(r'src="([^"]+)', iframe).group(1)
        except:
            return None # Probably a temporary block, or change in embedded code.

     embedURL = None

     # On rare cases an episode might have several "chapters", which are video players on the page.
     embedURLPattern = b'onclick="myFunction'
     embedURLIndex = content.find(embedURLPattern)
     if 'playChapters' in params or ADDON.getSetting('chapterEpisodes') == 'true':
        # Multi-chapter episode found (that is, multiple embedURLPattern statements found).
        # Extract all chapters from the page.
        embedURLPatternLen = len(embedURLPattern)
        currentPlayerIndex = embedURLIndex
        dataIndices = [ ]
        while currentPlayerIndex != -1:
            dataIndices.append(currentPlayerIndex)
            currentPlayerIndex = content.find(embedURLPattern, currentPlayerIndex + embedURLPatternLen)

        # If more than one "embedURL" statement found, make a selection dialog and call them "chapters".
        if len(dataIndices) > 1:
            selectedIndex = xbmcgui.Dialog().select(
                'Select Chapter', ['Chapter '+str(n) for n in range(1, len(dataIndices)+1)]
            )
        else:
            selectedIndex = 0

        if selectedIndex != -1:
            embedURL = _decodeSource(content[dataIndices[selectedIndex]:])
        else:
            return # User cancelled the chapter selection.
     else:
        # Normal / single-chapter episode.
        embedURL = _decodeSource(content[embedURLIndex:])
        # User asked to play multiple chapters, but only one chapter/video player found.
        if embedURL and 'playChapters' in params:
            xbmcgui.Dialog().notification('WatchNixtoons2', 'Only 1 chapter found...', ADDON_ICON, 2000, False)

     # Handle temporary blocks / failures.
     if not embedURL:
        if 'high volume of requests' in content:
            xbmcgui.Dialog().ok(
                'WatchNixtoons2 Fail (Server Response)',
                '"We are getting extremely high volume of requests on our video servers so that we temporarily block for free videos for free users. I apologize for the inconvenience."'
            )
        return

     # Request the embedded player page.
     r2 = requestHelper(unescapeHTMLText(embedURL)) # Sometimes a '&#038;' symbol is present in this URL.
     html = r2.text

     # Find the stream URLs.
     if 'getvid?evid' in html:
        # Query-style stream getting.
        sourceURL = re.search(b'"(/inc/embed/getvidlink[^"]+)', html, re.DOTALL).group(1)

        # Inline code similar to 'requestHelper()'.
        # The User-Agent for this next request is somehow encoded into the media tokens, so we make sure to use
        # the EXACT SAME value later, when playing the media, or else we get a HTTP 404 / 500 error.
        r3 = requestHelper(
            BASEURL + sourceURL,
            data = None,
            extraHeaders = {
                'User-Agent': WNT2_USER_AGENT, 'Accept': '*/*', 'Referer': embedURL, 'X-Requested-With': 'XMLHttpRequest'
            }
        )
        if not r3.ok:
            raise Exception('Sources XMLHttpRequest request failed')
        jsonData = r3.json()

        # Only two qualities are ever available: 480p ("SD") and 720p ("HD").
        sourceURLs = [ ]
        sdToken = jsonData.get('enc', '')
        hdToken = jsonData.get('hd', '')
        sourceBaseURL = jsonData.get('server', '') + '/getvid?evid='
        if sdToken:
            sourceURLs.append(('480 (SD)', sourceBaseURL + sdToken)) # Order the items as (LABEL, URL).
        if hdToken:
            sourceURLs.append(('720 (HD)', sourceBaseURL + hdToken))
        # Use the same backup stream method as the source: cdn domain + SD stream.
        backupURL = jsonData.get('cdn', '') + '/getvid?evid=' + (sdToken or hdToken)
     else:
        # Alternative video player page, with plain stream links in the JWPlayer javascript.
        sourcesBlock = re.search('sources:\s*?\[(.*?)\]', html, re.DOTALL).group(1)
        streamPattern = re.compile('\{\s*?file:\s*?"(.*?)"(?:,\s*?label:\s*?"(.*?)")?')
        sourceURLs = [
            # Order the items as (LABEL (or empty string), URL).
            (sourceMatch.group(2), sourceMatch.group(1))
            for sourceMatch in streamPattern.finditer(sourcesBlock)
        ]
        # Use the backup link in the 'onError' handler of the 'jw' player.
        backupMatch = streamPattern.search(html[html.find(b'jw.onError'):])
        backupURL = backupMatch.group(1) if backupMatch else ''

     mediaURL = None
     if len(sourceURLs) >= 1: # Just want the SD quality as server may be busy.
        mediaURL = sourceURLs[0][1]
#     elif len(sourceURLs) > 0:
        # Always force "select quality" for now.
#        playbackMethod = ADDON.getSetting('playbackMethod')
#        if playbackMethod == '0': # Select quality.
#                selectedIndex = xbmcgui.Dialog().select(
#                    'Select Quality', [(sourceItem[0] or '?') for sourceItem in sourceURLs]
#                )
#                if selectedIndex != -1:
#                    mediaURL = sourceURLs[selectedIndex][1]
#        else: # Auto-play user choice.
#            sortedSources = sorted(sourceURLs)
#            mediaURL = sortedSources[-1][1] if playbackMethod == '1' else sortedSources[0][1]
#        mediaURL = sourceURLs[0][1]

     if mediaURL:
        # Kodi headers for playing web streamed media.
#        global MEDIA_HEADERS
        if not MEDIA_HEADERS:
            MEDIA_HEADERS = {
                'User-Agent': WNT2_USER_AGENT,
                'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
                'Connection': 'keep-alive',
                'Verifypeer': 'false',
                'Referer': BASEURL + '/'
            }

        # Try to un-redirect the chosen media URL.
        # If it fails, try to un-resolve the backup URL. If not even the backup URL is working, abort playing.
        mediaHead = solveMediaRedirect(mediaURL, MEDIA_HEADERS)
        if not mediaHead:
            mediaHead = solveMediaRedirect(backupURL, MEDIA_HEADERS)
        if not mediaHead:
            return xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())

        # Need to use the exact same ListItem name & infolabels when playing or else Kodi replaces that item
        # in the UI listing.
        item = xbmcgui.ListItem(xbmc.getInfoLabel('ListItem.Label'))
        item.setPath(mediaHead.url + '|' + '&'.join(key+'='+quote_plus(val) for key, val in MEDIA_HEADERS.items()))
        item.setMimeType(mediaHead.headers.get('Content-Type', 'video/mp4')) # Avoids Kodi's MIME request.

        # When coming in from a Favourite item, there will be no metadata. Try to get at least a title.
        itemTitle = xbmc.getInfoLabel('ListItem.Title')
        if not itemTitle:
            match = re.search(b'<h1[^>]+>([^<]+)</h1', content)
            if match:
                itemTitle = match.group(1).replace(' English Subbed', '', 1).replace( 'English Dubbed', '', 1)
            else:
                itemTitle = ''

        episodeString = xbmc.getInfoLabel('ListItem.Episode')
        if episodeString != '' and episodeString != '-1':
            seasonInfoLabel = xbmc.getInfoLabel('ListItem.Season')
            item.setInfo('video',
                {
                    'tvshowtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
                    'title': itemTitle,
                    'season': int(seasonInfoLabel) if seasonInfoLabel.isdigit() else -1,
                    'episode': int(episodeString),
                    'plot': xbmc.getInfoLabel('ListItem.Plot'),
                    'mediatype': 'episode'
                }
            )
        else:
            item.setInfo('video',
                {
                    'title': itemTitle,
                    'plot': xbmc.getInfoLabel('ListItem.Plot'),
                    'mediatype': 'movie'
                }
            )

        #xbmc.Player().play(listitem=item) # Alternative play method, lets you extend the Player class with your own.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, True, item)
     else:
		# Failed. No source found, or the user didn't select one from the dialog.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())

    MEDIA_HEADERS = None
    try:
        premiumtest = requests.head(mediaURL, timeout=10, allow_redirects=True)
    except requests.exceptions.RequestException as error:
        premiumtest = error
#    premiumtest = requests.head(mediaURL, timeout=1)
    if str(premiumtest) == "<Response [200]>": #Test if the premium link is accessible if not, let's try the free version.
        if not MEDIA_HEADERS:
                MEDIA_HEADERS = {
					'User-Agent': WNT2_USER_AGENT,
					'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
					'Connection': 'keep-alive',
					'Verifypeer': 'false',
					'Referer': BASEURL + '/'
				}
        mediaHead = solveMediaRedirect(mediaURL, MEDIA_HEADERS)
        item = xbmcgui.ListItem(xbmc.getInfoLabel('ListItem.Label'))
        item.setPath(mediaHead.url + '|' + '&'.join(key+'='+quote_plus(val) for key, val in MEDIA_HEADERS.items()))
        item.setMimeType(mediaHead.headers.get('Content-Type', 'video/mp4')) # Avoids Kodi's MIME request.
			# When coming in from a Favourite item, there will be no metadata. Try to get at least a title.
        itemTitle = xbmc.getInfoLabel('ListItem.Title')
        if not itemTitle:
                match = re.search(b'<h1[^>]+>([^<]+)</h1', content)
                if match:
                    itemTitle = match.group(1).replace(' English Subbed', '', 1).replace( 'English Dubbed', '', 1)
                else:
                    itemTitle = ''

        episodeString = xbmc.getInfoLabel('ListItem.Episode')
        if episodeString != '' and episodeString != '-1':
                seasonInfoLabel = xbmc.getInfoLabel('ListItem.Season')
                item.setInfo('video',
					{
						'tvshowtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
						'title': itemTitle,
						'season': int(seasonInfoLabel) if seasonInfoLabel.isdigit() else -1,
						'episode': int(episodeString),
						'plot': xbmc.getInfoLabel('ListItem.Plot'),
						'mediatype': 'episode'
					}
				)
        else:
                item.setInfo('video',
					{
						'title': itemTitle,
						'plot': xbmc.getInfoLabel('ListItem.Plot'),
						'mediatype': 'movie'
					}
				)

		#xbmc.Player().play(listitem=item) # Alternative play method, lets you extend the Player class with your own.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, True, item)
    elif '/inc/embed' in content: #Premium link failed so we'll try the free version now.
     xbmcgui.Dialog().notification('Trying free stream', '')
     r = requestHelper(url.replace('user.wco.tv', 'www.thewatchcartoononline.tv', 1)) # Change from premium site to free site
     content = r.content

     def _decodeSource(subContent):
        chars = subContent[subContent.find('[') : subContent.find(']')]
        spread = int(re.search(r' - (\d+)\)\; }', subContent[subContent.find(' - '):]).group(1))
        iframe = ''.join(
            chr(
                int(''.join(c for c in b64decode(char) if c.isdigit())) - spread
            )
            for char in chars.replace('"', '').split(',')
        )
        try:
            return BASEURL + re.search(r'src="([^"]+)', iframe).group(1)
        except:
            return None # Probably a temporary block, or change in embedded code.

     embedURL = None

     # On rare cases an episode might have several "chapters", which are video players on the page.
     embedURLPattern = b'onclick="myFunction'
     embedURLIndex = content.find(embedURLPattern)
     if 'playChapters' in params or ADDON.getSetting('chapterEpisodes') == 'true':
        # Multi-chapter episode found (that is, multiple embedURLPattern statements found).
        # Extract all chapters from the page.
        embedURLPatternLen = len(embedURLPattern)
        currentPlayerIndex = embedURLIndex
        dataIndices = [ ]
        while currentPlayerIndex != -1:
            dataIndices.append(currentPlayerIndex)
            currentPlayerIndex = content.find(embedURLPattern, currentPlayerIndex + embedURLPatternLen)

        # If more than one "embedURL" statement found, make a selection dialog and call them "chapters".
        if len(dataIndices) > 1:
            selectedIndex = xbmcgui.Dialog().select(
                'Select Chapter', ['Chapter '+str(n) for n in range(1, len(dataIndices)+1)]
            )
        else:
            selectedIndex = 0

        if selectedIndex != -1:
            embedURL = _decodeSource(content[dataIndices[selectedIndex]:])
        else:
            return # User cancelled the chapter selection.
     else:
        # Normal / single-chapter episode.
        embedURL = _decodeSource(content[embedURLIndex:])
        # User asked to play multiple chapters, but only one chapter/video player found.
        if embedURL and 'playChapters' in params:
            xbmcgui.Dialog().notification('WatchNixtoons2', 'Only 1 chapter found...', ADDON_ICON, 2000, False)

     # Handle temporary blocks / failures.
     if not embedURL:
        if 'high volume of requests' in content:
            xbmcgui.Dialog().ok(
                'WatchNixtoons2 Fail (Server Response)',
                '"We are getting extremely high volume of requests on our video servers so that we temporarily block for free videos for free users. I apologize for the inconvenience."'
            )
        return

     # Request the embedded player page.
     r2 = requestHelper(unescapeHTMLText(embedURL)) # Sometimes a '&#038;' symbol is present in this URL.
     html = r2.text

     # Find the stream URLs.
     if 'getvid?evid' in html:
        # Query-style stream getting.
        sourceURL = re.search(b'"(/inc/embed/getvidlink[^"]+)', html, re.DOTALL).group(1)

        # Inline code similar to 'requestHelper()'.
        # The User-Agent for this next request is somehow encoded into the media tokens, so we make sure to use
        # the EXACT SAME value later, when playing the media, or else we get a HTTP 404 / 500 error.
        r3 = requestHelper(
            BASEURL + sourceURL,
            data = None,
            extraHeaders = {
                'User-Agent': WNT2_USER_AGENT, 'Accept': '*/*', 'Referer': embedURL, 'X-Requested-With': 'XMLHttpRequest'
            }
        )
        if not r3.ok:
            raise Exception('Sources XMLHttpRequest request failed')
        jsonData = r3.json()

        # Only two qualities are ever available: 480p ("SD") and 720p ("HD").
        sourceURLs = [ ]
        sdToken = jsonData.get('enc', '')
        hdToken = jsonData.get('hd', '')
        sourceBaseURL = jsonData.get('server', '') + '/getvid?evid='
        if sdToken:
            sourceURLs.append(('480 (SD)', sourceBaseURL + sdToken)) # Order the items as (LABEL, URL).
        if hdToken:
            sourceURLs.append(('720 (HD)', sourceBaseURL + hdToken))
        # Use the same backup stream method as the source: cdn domain + SD stream.
        backupURL = jsonData.get('cdn', '') + '/getvid?evid=' + (sdToken or hdToken)
     else:
        # Alternative video player page, with plain stream links in the JWPlayer javascript.
        sourcesBlock = re.search('sources:\s*?\[(.*?)\]', html, re.DOTALL).group(1)
        streamPattern = re.compile('\{\s*?file:\s*?"(.*?)"(?:,\s*?label:\s*?"(.*?)")?')
        sourceURLs = [
            # Order the items as (LABEL (or empty string), URL).
            (sourceMatch.group(2), sourceMatch.group(1))
            for sourceMatch in streamPattern.finditer(sourcesBlock)
        ]
        # Use the backup link in the 'onError' handler of the 'jw' player.
        backupMatch = streamPattern.search(html[html.find(b'jw.onError'):])
        backupURL = backupMatch.group(1) if backupMatch else ''

     mediaURL = None
     if len(sourceURLs) >= 1: # Just want the SD quality as server may be busy.
        mediaURL = sourceURLs[0][1]
#     elif len(sourceURLs) > 0:
        # Always force "select quality" for now.
#        playbackMethod = ADDON.getSetting('playbackMethod')
#        if playbackMethod == '0': # Select quality.
#                selectedIndex = xbmcgui.Dialog().select(
#                    'Select Quality', [(sourceItem[0] or '?') for sourceItem in sourceURLs]
#                )
#                if selectedIndex != -1:
#                    mediaURL = sourceURLs[selectedIndex][1]
#        else: # Auto-play user choice.
#            sortedSources = sorted(sourceURLs)
#            mediaURL = sortedSources[-1][1] if playbackMethod == '1' else sortedSources[0][1]
#        mediaURL = sourceURLs[0][1]

     if mediaURL:
        # Kodi headers for playing web streamed media.
#        global MEDIA_HEADERS
        if not MEDIA_HEADERS:
            MEDIA_HEADERS = {
                'User-Agent': WNT2_USER_AGENT,
                'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
                'Connection': 'keep-alive',
                'Verifypeer': 'false',
                'Referer': BASEURL + '/'
            }

        # Try to un-redirect the chosen media URL.
        # If it fails, try to un-resolve the backup URL. If not even the backup URL is working, abort playing.
        mediaHead = solveMediaRedirect(mediaURL, MEDIA_HEADERS)
        if not mediaHead:
            mediaHead = solveMediaRedirect(backupURL, MEDIA_HEADERS)
        if not mediaHead:
            return xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())

        # Need to use the exact same ListItem name & infolabels when playing or else Kodi replaces that item
        # in the UI listing.
        item = xbmcgui.ListItem(xbmc.getInfoLabel('ListItem.Label'))
        item.setPath(mediaHead.url + '|' + '&'.join(key+'='+quote_plus(val) for key, val in MEDIA_HEADERS.items()))
        item.setMimeType(mediaHead.headers.get('Content-Type', 'video/mp4')) # Avoids Kodi's MIME request.

        # When coming in from a Favourite item, there will be no metadata. Try to get at least a title.
        itemTitle = xbmc.getInfoLabel('ListItem.Title')
        if not itemTitle:
            match = re.search(b'<h1[^>]+>([^<]+)</h1', content)
            if match:
                itemTitle = match.group(1).replace(' English Subbed', '', 1).replace( 'English Dubbed', '', 1)
            else:
                itemTitle = ''

        episodeString = xbmc.getInfoLabel('ListItem.Episode')
        if episodeString != '' and episodeString != '-1':
            seasonInfoLabel = xbmc.getInfoLabel('ListItem.Season')
            item.setInfo('video',
                {
                    'tvshowtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
                    'title': itemTitle,
                    'season': int(seasonInfoLabel) if seasonInfoLabel.isdigit() else -1,
                    'episode': int(episodeString),
                    'plot': xbmc.getInfoLabel('ListItem.Plot'),
                    'mediatype': 'episode'
                }
            )
        else:
            item.setInfo('video',
                {
                    'title': itemTitle,
                    'plot': xbmc.getInfoLabel('ListItem.Plot'),
                    'mediatype': 'movie'
                }
            )

        #xbmc.Player().play(listitem=item) # Alternative play method, lets you extend the Player class with your own.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, True, item)
    else:
		# Failed. No source found, or the user didn't select one from the dialog.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())
	
#Mod by Christian Haitian ends here

   else:
        # Needs to be the BASEURL domain to get multiple video qualities.
    url = params['url']
    # Sanitize the URL since on some occasions it's a path instead of full address.
    url = url if url.startswith('http') else (BASEURL + (url if url.startswith('/') else '/' + url))
    r = requestHelper(url.replace('watchcartoononline.io', 'thewatchcartoononline.tv', 1)) # New domain safety.
    content = r.content

    def _decodeSource(subContent):
        chars = subContent[subContent.find('[') : subContent.find(']')]
        spread = int(re.search(r' - (\d+)\)\; }', subContent[subContent.find(' - '):]).group(1))
        iframe = ''.join(
            chr(
                int(''.join(c for c in b64decode(char) if c.isdigit())) - spread
            )
            for char in chars.replace('"', '').split(',')
        )
        try:
            return BASEURL + re.search(r'src="([^"]+)', iframe).group(1)
        except:
            return None # Probably a temporary block, or change in embedded code.

    embedURL = None

    # On rare cases an episode might have several "chapters", which are video players on the page.
    embedURLPattern = b'onclick="myFunction'
    embedURLIndex = content.find(embedURLPattern)
    if 'playChapters' in params or ADDON.getSetting('chapterEpisodes') == 'true':
        # Multi-chapter episode found (that is, multiple embedURLPattern statements found).
        # Extract all chapters from the page.
        embedURLPatternLen = len(embedURLPattern)
        currentPlayerIndex = embedURLIndex
        dataIndices = [ ]
        while currentPlayerIndex != -1:
            dataIndices.append(currentPlayerIndex)
            currentPlayerIndex = content.find(embedURLPattern, currentPlayerIndex + embedURLPatternLen)

        # If more than one "embedURL" statement found, make a selection dialog and call them "chapters".
        if len(dataIndices) > 1:
            selectedIndex = xbmcgui.Dialog().select(
                'Select Chapter', ['Chapter '+str(n) for n in range(1, len(dataIndices)+1)]
            )
        else:
            selectedIndex = 0

        if selectedIndex != -1:
            embedURL = _decodeSource(content[dataIndices[selectedIndex]:])
        else:
            return # User cancelled the chapter selection.
    else:
        # Normal / single-chapter episode.
        embedURL = _decodeSource(content[embedURLIndex:])
        # User asked to play multiple chapters, but only one chapter/video player found.
        if embedURL and 'playChapters' in params:
            xbmcgui.Dialog().notification('WatchNixtoons2', 'Only 1 chapter found...', ADDON_ICON, 2000, False)

    # Handle temporary blocks / failures.
    if not embedURL:
        if 'high volume of requests' in content:
            xbmcgui.Dialog().ok(
                'WatchNixtoons2 Fail (Server Response)',
                '"We are getting extremely high volume of requests on our video servers so that we temporarily block for free videos for free users. I apologize for the inconvenience."'
            )
        return

    # Request the embedded player page.
    r2 = requestHelper(unescapeHTMLText(embedURL)) # Sometimes a '&#038;' symbol is present in this URL.
    html = r2.text

    # Find the stream URLs.
    if 'getvid?evid' in html:
        # Query-style stream getting.
        sourceURL = re.search(b'"(/inc/embed/getvidlink[^"]+)', html, re.DOTALL).group(1)

        # Inline code similar to 'requestHelper()'.
        # The User-Agent for this next request is somehow encoded into the media tokens, so we make sure to use
        # the EXACT SAME value later, when playing the media, or else we get a HTTP 404 / 500 error.
        r3 = requestHelper(
            BASEURL + sourceURL,
            data = None,
            extraHeaders = {
                'User-Agent': WNT2_USER_AGENT, 'Accept': '*/*', 'Referer': embedURL, 'X-Requested-With': 'XMLHttpRequest'
            }
        )
        if not r3.ok:
            raise Exception('Sources XMLHttpRequest request failed')
        jsonData = r3.json()

        # Only two qualities are ever available: 480p ("SD") and 720p ("HD").
        sourceURLs = [ ]
        sdToken = jsonData.get('enc', '')
        hdToken = jsonData.get('hd', '')
        sourceBaseURL = jsonData.get('server', '') + '/getvid?evid='
        if sdToken:
            sourceURLs.append(('480 (SD)', sourceBaseURL + sdToken)) # Order the items as (LABEL, URL).
        if hdToken:
            sourceURLs.append(('720 (HD)', sourceBaseURL + hdToken))
        # Use the same backup stream method as the source: cdn domain + SD stream.
        backupURL = jsonData.get('cdn', '') + '/getvid?evid=' + (sdToken or hdToken)
    else:
        # Alternative video player page, with plain stream links in the JWPlayer javascript.
        sourcesBlock = re.search('sources:\s*?\[(.*?)\]', html, re.DOTALL).group(1)
        streamPattern = re.compile('\{\s*?file:\s*?"(.*?)"(?:,\s*?label:\s*?"(.*?)")?')
        sourceURLs = [
            # Order the items as (LABEL (or empty string), URL).
            (sourceMatch.group(2), sourceMatch.group(1))
            for sourceMatch in streamPattern.finditer(sourcesBlock)
        ]
        # Use the backup link in the 'onError' handler of the 'jw' player.
        backupMatch = streamPattern.search(html[html.find(b'jw.onError'):])
        backupURL = backupMatch.group(1) if backupMatch else ''

    mediaURL = None
    if len(sourceURLs) == 1: # Only one quality available.
        mediaURL = sourceURLs[0][1]
    elif len(sourceURLs) > 0:
        # Always force "select quality" for now.
        playbackMethod = ADDON.getSetting('playbackMethod')
        if playbackMethod == '0': # Select quality.
                selectedIndex = xbmcgui.Dialog().select(
                    'Select Quality', [(sourceItem[0] or '?') for sourceItem in sourceURLs]
                )
                if selectedIndex != -1:
                    mediaURL = sourceURLs[selectedIndex][1]
        else: # Auto-play user choice.
            sortedSources = sorted(sourceURLs)
            mediaURL = sortedSources[-1][1] if playbackMethod == '1' else sortedSources[0][1]

    if mediaURL:
        # Kodi headers for playing web streamed media.
#        global MEDIA_HEADERS
        if not MEDIA_HEADERS:
            MEDIA_HEADERS = {
                'User-Agent': WNT2_USER_AGENT,
                'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
                'Connection': 'keep-alive',
                'Verifypeer': 'false',
                'Referer': BASEURL + '/'
            }

        # Try to un-redirect the chosen media URL.
        # If it fails, try to un-resolve the backup URL. If not even the backup URL is working, abort playing.
        mediaHead = solveMediaRedirect(mediaURL, MEDIA_HEADERS)
        if not mediaHead:
            mediaHead = solveMediaRedirect(backupURL, MEDIA_HEADERS)
        if not mediaHead:
            return xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())

        # Need to use the exact same ListItem name & infolabels when playing or else Kodi replaces that item
        # in the UI listing.
        item = xbmcgui.ListItem(xbmc.getInfoLabel('ListItem.Label'))
        item.setPath(mediaHead.url + '|' + '&'.join(key+'='+quote_plus(val) for key, val in MEDIA_HEADERS.items()))
        item.setMimeType(mediaHead.headers.get('Content-Type', 'video/mp4')) # Avoids Kodi's MIME request.

        # When coming in from a Favourite item, there will be no metadata. Try to get at least a title.
        itemTitle = xbmc.getInfoLabel('ListItem.Title')
        if not itemTitle:
            match = re.search(b'<h1[^>]+>([^<]+)</h1', content)
            if match:
                itemTitle = match.group(1).replace(' English Subbed', '', 1).replace( 'English Dubbed', '', 1)
            else:
                itemTitle = ''

        episodeString = xbmc.getInfoLabel('ListItem.Episode')
        if episodeString != '' and episodeString != '-1':
            seasonInfoLabel = xbmc.getInfoLabel('ListItem.Season')
            item.setInfo('video',
                {
                    'tvshowtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
                    'title': itemTitle,
                    'season': int(seasonInfoLabel) if seasonInfoLabel.isdigit() else -1,
                    'episode': int(episodeString),
                    'plot': xbmc.getInfoLabel('ListItem.Plot'),
                    'mediatype': 'episode'
                }
            )
        else:
            item.setInfo('video',
                {
                    'title': itemTitle,
                    'plot': xbmc.getInfoLabel('ListItem.Plot'),
                    'mediatype': 'movie'
                }
            )

        #xbmc.Player().play(listitem=item) # Alternative play method, lets you extend the Player class with your own.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, True, item)
    else:
        # Failed. No source found, or the user didn't select one from the dialog.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())

def buildURL(query):
    '''
    Helper function to build a Kodi xbmcgui.ListItem URL.
    :param query: Dictionary of url parameters to put in the URL.
    :returns: A formatted and urlencoded URL string.
    '''
    return (PLUGIN_URL + '?' + urlencode({k: v.encode('utf-8') if isinstance(v, str)
                                         else str(v, errors='ignore').encode('utf-8')
                                         for k, v in query.items()}))


def setViewMode():
    if ADDON.getSetting('useViewMode') == 'true':
        viewModeID = ADDON.getSetting('viewModeID')
        if viewModeID.isdigit():
            xbmc.executebuiltin('Container.SetViewMode(' + viewModeID + ')')


def xbmcDebug(*args):
    xbmc.log('WATCHNIXTOONS2 > ' + ' '.join((val if isinstance(val, str) else repr(val)) for val in args), xbmc.LOGWARNING)


def simpleRequest(url, requestFunc, headers):
    return requestFunc(url, headers=headers, verify=False, timeout=10)


# Thumbnail HTTP headers for Kodi to use when grabbing thumbnail images.
def getThumbnailHeaders():
    # Original code:
    #return (
    #    '|User-Agent='+quote_plus(WNT2_USER_AGENT)
    #    + '&Accept='+quote_plus('image/webp,*/*')
    #    + '&Referer='+quote_plus(BASEURL+'/')
    #)
    cookieProperty = getRawWindowProperty(PROPERTY_SESSION_COOKIE)
    cookies = ('&Cookie=' + quote_plus(cookieProperty)) if cookieProperty else ''

    # Since it's a constant value, it can be precomputed.
    return '|User-Agent=Mozilla%2F5.0+%28compatible%3B+WatchNixtoons2%2F0.4.1%3B' \
    '+%2Bhttps%3A%2F%2Fgithub.com%2Fdoko-desuka%2Fplugin.video.watchnixtoons2%29' \
    '&Verifypeer=false&Accept=image%2Fwebp%2C%2A%2F%2A&Referer=https%3A%2F%2Fwww.thewatchcartoononline.tv%2F' + cookies


def getOldDomains():
    # Old possible domains, in the order of likeliness.
    return (
        'www.wcostream.com', 'm.wcostream.com', 'www.watchcartoononline.io', 'm.watchcartoononline.io'
    )


def solveMediaRedirect(url, headers):
    # Use HEAD requests to fulfill possible 302 redirections.
    # Returns the final stream HEAD response.
    while True:
        try:
            mediaHead = simpleRequest(url, requests.head, headers)
            if 'Location' in mediaHead.headers:
                url = mediaHead.headers['Location'] # Change the URL to the redirected location.
            else:
                mediaHead.raise_for_status()
                return mediaHead # Return the response.
        except:
            return None # Return nothing on failure.


def requestHelper(url, data=None, extraHeaders=None):
    myHeaders = {
        'User-Agent': WNT2_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8',
        'Verifypeer': 'false',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'DNT': '1'
    }
    if extraHeaders:
        myHeaders.update(extraHeaders)

    # At the moment it's a single response cookie, "__cfduid". Other cookies are set w/ Javascript by ads.
    cookieProperty = getRawWindowProperty(PROPERTY_SESSION_COOKIE)
    if cookieProperty:
        cookieDict = dict(pair.split('=') for pair in cookieProperty.split('; '))
    else:
        cookieDict = None

    startTime = time()

#Mod by Christian Haitian starts here

    if data and BASEURL == 'https://user.wco.tv':
        response = session.post(url, data=data, headers=myHeaders, verify=False, timeout=10)
    elif data and BASEURL == 'https://www.thewatchcartoononline.tv':
        response = requests.post(url, data=data, headers=myHeaders, verify=False, cookies=cookieDict, timeout=10)
    else:
         if BASEURL == 'https://user.wco.tv': 
             response = session.get(url, headers=myHeaders, verify=False, timeout=10)
         else:
             response = requests.get(url, headers=myHeaders, verify=False, cookies=cookieDict, timeout=10)

#Mod by Christian Haitian ends here

    # Store the session cookie(s), if any.
    if not cookieProperty and response.cookies:
        setRawWindowProperty(
            PROPERTY_SESSION_COOKIE, '; '.join(pair[0]+'='+pair[1] for pair in response.cookies.get_dict().items())
        )

    elapsed = time() - startTime
    if elapsed < 1.5:
        sleep(1.5 - elapsed)

    return response


#def getRandomUserAgent():
#    # Random user-agent logic. Thanks to http://edmundmartin.com/random-user-agent-requests-python/
#    from random import choice
#    desktop_agents = (
#        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
#        'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
#        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
#        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/602.2.14 (KHTML, like Gecko) Version/10.0.1 Safari/602.2.14',
#        'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
#        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
#        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
#        'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
#        'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
#        'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0'
#    )
#    return choice(desktop_agents)


# Defined after all the functions exist.
CATALOG_FUNCS = {
    URL_PATHS['latest']: makeLatestCatalog,
    URL_PATHS['popular']: makePopularCatalog,
    URL_PATHS['search']: makeSearchCatalog
}


def main():
    '''
    Main add-on routing function, calls a certain action (function).
    The 'action' parameter is the direct name of the function.
    '''
    params = dict(parse_qsl(sys.argv[2][1:], keep_blank_values=True))
    globals()[params.get('action', 'actionMenu')](params) # Defaults to 'actionMenu()'.
