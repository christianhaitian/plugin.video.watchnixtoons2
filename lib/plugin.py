# -*- coding: utf-8 -*-
import re
import sys
import six

from itertools import chain
from six.moves import urllib_parse
from string import ascii_uppercase

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from lib.constants import *
from lib.common import *
from lib.network import rqs_get, request_helper
from lib.recently_watched import recently_watched_load, recently_watched_add, recently_watched_remove

from lib.integration.trakt_actions import *

if BASEURL_SETTING == 1:
    from lib.sites.wcoflix import *
elif BASEURL_SETTING == 2:
    from lib.sites.wcoforever import *
else:
    from lib.sites.wcostream import *

# language
__language__ = ADDON.getLocalizedString

def actionMenu(params):

    def _menuItem(title, data, color):
        item = xbmcgui.ListItem('[B][COLOR ' + color + ']' + title + '[/COLOR][/B]', label2 = title)
        item.setArt(ADDON_ICON_DICT)
        item_set_info( item, {'title': title, 'plot': title} )
        return (build_url(data), item, True)

    xbmcplugin.addDirectoryItems(
        PLUGIN_ID,
        (
            # Latest
            _menuItem( __language__(30050), {'action': 'actionCatalogMenu', 'path': URL_PATHS['latest']}, 'mediumaquamarine' ),
            # Latest Movies - Make the Latest Movies menu go straight to the item list, no catalog.
            _menuItem( __language__(30051), {'action': 'actionLatestMoviesMenu', 'path': URL_PATHS['latestmovies']}, 'mediumaquamarine'),
            # Ongoing & Popular
            _menuItem( __language__(30052), {'action': 'actionCatalogMenu', 'path': URL_PATHS['popular']}, 'mediumaquamarine'),
            # Dubbed
            _menuItem( __language__(30053), {'action': 'actionCatalogMenu', 'path': URL_PATHS['dubbed']}, 'lightgreen'),
            # Cartoons
            _menuItem( __language__(30054), {'action': 'actionCatalogMenu', 'path': URL_PATHS['cartoons']}, 'lightgreen'),
            # Subbed
            _menuItem( __language__(30055), {'action': 'actionCatalogMenu', 'path': URL_PATHS['subbed']}, 'lightgreen'),
            # Movies
            _menuItem( xbmc.getLocalizedString(342), {'action': 'actionCatalogMenu', 'path': URL_PATHS['movies']}, 'lightgreen'),
            # OVAs
            _menuItem( __language__(30056), {'action': 'actionCatalogMenu', 'path': URL_PATHS['ova']}, 'lightgreen'),
            # Recently Watched
            _menuItem( __language__(30057), {'action': 'actionRecentlyWatchedMenu', 'path': 'recently_watched'}, 'orange'),
            # Search - Non-web path.
            _menuItem( xbmc.getLocalizedString(137), {'action': 'actionSearchMenu',  'path': 'search'}, 'lavender'),
            # Settings - Non-web path.
            _menuItem( xbmc.getLocalizedString(1390), {'action': 'actionShowSettings','path': 'settings'}, 'lavender')
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
                art_dict = {'thumb': None}
                for sectionName in sorted(catalog.keys()):
                    if catalog[sectionName]:
                        item = xbmcgui.ListItem(sectionName)
                        # Correct the address for the '#' (miscellaneous, non-letter) category.
                        art_dict['thumb'] = THUMBS_BASEURL + ('0' if sectionName == '#' else sectionName) + '.png'
                        item.setArt(art_dict)
                        item_set_info( item, {'plot': sectionName} )
                        items.append(
                            (
                                build_url({'action': 'actionCatalogSection', 'path': params['path'], 'section': sectionName}),
                                item,
                                True
                            )
                        )
            else:
                items = [
                    (
                        build_url({'action': 'actionCatalogSection', 'path': params['path'], 'section': sectionName}),
                        xbmcgui.ListItem(sectionName),
                        True
                    )
                    for sectionName in sorted(catalog.keys()) if len(catalog[sectionName])
                ]
            # See if an "All" folder is necessary (when there's more than one folder in the catalog).
            if len(items) > 1:
                section_all = (
                    build_url({'action': 'actionCatalogSection', 'path': params['path'], 'section': 'ALL'}),
                    xbmcgui.ListItem('All'),
                    True
                )
                if ADDON_CATALOG_THUMBS:
                    art_dict['thumb'] = THUMBS_BASEURL + 'ALL.png'
                    section_all[1].setArt(art_dict)
                    item_set_info( section_all[1], {'plot': 'All'} )
                return [section_all] + items

            return items

        items = _catalogMenuItemsMake()
        if items:
            if len(items) > 1:
                xbmcplugin.addDirectoryItems(PLUGIN_ID, items)
            else:
                # Conveniency when a search leads to only 1 result,
                # show it already without the catalog screen.
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

    # Set up a boolean indicating if the catalog items are already playable,
    # instead of being folders with more items inside.
    # This is true for the OVA, movies, latest-episodes, movie-search and episode-search catalogs.
    # Items in these catalogs link to the video player pages already.
    is_special = (
        path in {URL_PATHS['ova'], URL_PATHS['movies'], URL_PATHS['latest']}
        # not series = movies or episodes search
        or params.get('searchType', 'series') not in {'series', 'genres'}
    )

    if is_special:
        action = 'actionResolve'
        is_folder = False
    else:
        action = 'actionEpisodesMenu'
        is_folder = True

    art_dict = ADDON_ICON_DICT

    thumb = params.get('thumb', ADDON_ICON)
    if path != URL_PATHS['latest'] or not ADDON_LATEST_THUMBS:
        if thumb:
            art_dict = {'icon': thumb, 'thumb': thumb, 'poster': thumb}
    elif thumb:
        art_dict[ 'icon' ] = thumb

    # Persistent property with item metadata, used with the "Show Information" context menu.
    infoItems = getWindowProperty(PROPERTY_INFO_ITEMS) or { }

    if 'query' not in params and ADDON.getSetting('cleanupEpisodes') == 'true':
        listItemFunc = makeListItemClean
    else:
        listItemFunc = makeListItem

    if params['section'] == 'ALL':
        section_items = chain.from_iterable(catalog[sectionName] for sectionName in sorted(catalog))
    else:
        section_items = catalog[params['section']]

    def _sectionItemsGen():

        # init variables for deciding how list items are going to be displayed
        show_thumbs = False
        show_fanart = False
        from_hash = False

        if path == URL_PATHS['latest']:

            if ADDON_LATEST_THUMBS:
                show_thumbs = True

            if ADDON_VIDEO_FANART:
                show_fanart = True

        elif ADDON_POPULAR_THUMBS and path == URL_PATHS['popular']:

            show_thumbs = True
            from_hash = True
            hashes = {}

            # get all hash files and combine as could be in any of them
            for path_tmp in [ URL_PATHS['dubbed'], URL_PATHS['cartoons'], URL_PATHS['subbed'] ]:
                hashes.update( hash_file_get( path_tmp ) )

        elif ADDON_SERIES_THUMBS and path in [ URL_PATHS['dubbed'], URL_PATHS['cartoons'], URL_PATHS['subbed'] ]:

            show_thumbs = True
            from_hash = True

            hashes = hash_file_get( path )

        elif path in [ URL_PATHS['movies'], URL_PATHS['ova'] ]:

            if ADDON_SERIES_THUMBS:

                show_thumbs = True
                from_hash = True

                hashes = hash_file_get( path )

            # we can also use the fanart for movies and OVAs
            if ADDON_VIDEO_FANART:
                show_fanart = True

        elif path == URL_PATHS[ 'search' ] and params.get('searchType', False) == 'series':
            show_thumbs = True

        # loop through entries and decide what to show
        for entry in section_items:

            # removes base so can be used in hash table
            entry_url = base_url_remove( BASEURL, entry[0] )
            img_url = entry_url.replace( '?season=all', '/season=all' )
            img_url = img_url.replace( '/season=all&lang=sub', '' ).replace( '/season=all&lang=dub', '' )
            img_url = img_url.replace( '/season=all&lang=cartoon', '' ).replace( '/season=all', '' )
            entry_art = art_dict

            # If there's metadata for this entry (requested by the user with "Show Information"), use it.
            if entry_url in infoItems:
                entryParams = None
                entry_plot, item_thumb = infoItems[entry_url]
                entry_art = {'icon': item_thumb, 'thumb': item_thumb, 'poster': item_thumb}
            else:

                # do this here so we only need to create a hash once per entry
                if show_thumbs and from_hash:
                    url_hash = generate_md5( img_url )

                # Decide what artwork to show
                if show_thumbs and from_hash is False:

                    if entry[2]:
                        # there were cases of thumbnail URL just consisting of 'https:'
                        # so back up to get thumbnail from fanart
                        if entry[2] == 'https:':
                            entry[2] = IMAGES_URL + '/thumbs' + img_url + '.jpg'

                        entry_art[ 'thumb' ] = entry[2]
                        entry_art[ 'poster' ] = entry[2]

                elif show_thumbs and from_hash and hashes.get( url_hash, False ):
                    thumb_from_hash = thumb_path_get( hashes.get( url_hash, '' ) )
                    entry_art = {'icon': thumb_from_hash, 'thumb': thumb_from_hash, 'poster': thumb_from_hash}

                entry_plot = ''
                entryParams = params

            # add fanart if option is selected
            # this is added last so is not affected by anything else
            if show_fanart:
                entry_art['fanart'] = IMAGES_URL + '/thumbs' + img_url + '.jpg'

            yield (
                build_url({'action': action, 'url': entry_url}),
                listItemFunc(entry[1], entry_url, entry_art, entry_plot, is_folder, is_special, entryParams),
                is_folder
            )

    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_sectionItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    setViewMode() # Set the skin layout mode if the option is enabled.

def actionEpisodesMenu(params):

    xbmcplugin.setContent(PLUGIN_ID, 'episodes')

    # Memory-cache the last episode list, to help when the user goes back and forth while watching
    # multiple episodes of the same show. This way only one web request is needed for the same show.
    lastListURL = getRawWindowProperty(PROPERTY_EPISODE_LIST_URL)
    if lastListURL and lastListURL == params['url']:
        listData = getWindowProperty(PROPERTY_EPISODE_LIST_DATA)
    else:
        # New domain safety replace, in case the user is coming in from an old Kodi favorite item.
        url = params['url'].replace('wcofun.tv', 'wcofun.net', 1)
        r = request_helper( ensure_full_url( BASEURL, url ) )
        html = r.text

        plot, thumb = getPageMetadata(html)

        data_start_index = html.find( SITE_SETTINGS[ 'episode' ][ 'start' ] )
        if data_start_index == -1:
            raise Exception('Episode list scrape fail: ' + url)

        # Episode list data: a tuple with the thumb, plot and an inner tuple of per-episode data.
        listData = (
            thumb,
            plot,
            tuple(
                (match.group('link'), match.group('name'), match.group('type'))
                for match in re.finditer(
                    SITE_SETTINGS[ 'episode' ][ 'regex' ], html[data_start_index : html.find( SITE_SETTINGS[ 'episode' ][ 'end' ] )]
                )
            )
        )
        setRawWindowProperty(PROPERTY_EPISODE_LIST_URL, params['url'])
        setWindowProperty(PROPERTY_EPISODE_LIST_DATA, listData)

    def _episodeItemsGen():

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()

        # use default addon dict by default
        art_dict = ADDON_ICON_DICT

        thumb = listData[0]
        if thumb:
            art_dict = {'icon': thumb, 'thumb': thumb, 'poster': thumb}
        
        plot = listData[1]

        listItemFunc = makeListItemClean if ADDON.getSetting('cleanupEpisodes') == 'true' else makeListItem

        item_params = {'action': 'actionResolve', 'url': None}
        listIter = iter(listData[2]) if ADDON.getSetting('reverseEpisodes') == 'true' else reversed(listData[2])

        for url, title, episode_type in listIter:

            # get language selected from url
            show_type = re.search(r'lang=(dub|sub)', params['url'])
            if show_type:
                show_type = str(show_type.group(1))

                # apply validation to lang variables
                # then skip episode if do not need to show it
                if episode_type and episode_type in LANG_TYPES and episode_type != show_type:
                    continue

            # add fanart if option is selected
            if ADDON_VIDEO_FANART:
                art_dict['fanart'] = url.replace( BASEURL, IMAGES_URL + '/thumbs' ) + '.jpg'

            url = base_url_remove( BASEURL, url )

            item = listItemFunc(title, url, art_dict, plot, is_folder=False, is_special=False, oldParams=None)
            item_params['url'] = url
            item_url = build_url(item_params)
            playlist.add(item_url, item)
            yield (item_url, item, False)

    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_episodeItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)

def actionLatestMoviesMenu(params):

    """
    Returns a list of links from a hidden '/anime/movies' area.
    Since this page is large, we memory cache it after it's been requested.
    """

    html = getRawWindowProperty(PROPERTY_LATEST_MOVIES)
    if not html:
        r = request_helper(BASEURL + params['path'])
        html = r.text
        setRawWindowProperty(PROPERTY_LATEST_MOVIES, html)

    # Similar scraping logic to 'actionEpisodesMenu()'.

    data_start_index = html.find( SITE_SETTINGS[ 'latest_movies' ][ 'start' ] )
    if data_start_index == -1:
        raise Exception('Latest movies scrape fail')

    # Persistent property with item metadata.
    infoItems = getWindowProperty(PROPERTY_INFO_ITEMS) or { }

    if ADDON_SERIES_THUMBS:
        # get required hash file for thumbnails
        hashes = hash_file_get( 'movie-list' )

    def _movieItemsGen():

        reIter = re.finditer(
            SITE_SETTINGS[ 'latest_movies' ][ 'regex' ], html[data_start_index : html.find( SITE_SETTINGS[ 'latest_movies' ][ 'end' ] )]
        )

        # The page has like 6000 items going back to 2010, so we limit to only the latest 200.
        for x in range(200):

            # use default addon dict by default
            art_dict = ADDON_ICON_DICT

            entry_url, entry_title = next(reIter).groups()

            if ADDON_SERIES_THUMBS:
                entry_hash = generate_md5( entry_url.replace( BASEURL, '' ) )
                if entry_hash in hashes.keys():
                    thumb_from_hash = thumb_path_get( hashes.get( entry_hash, '' ) )
                    art_dict = {'icon': ADDON_ICON, 'thumb': thumb_from_hash, 'poster': thumb_from_hash}

            if entry_url in infoItems:
                entryPlot, entryThumb = infoItems[entry_url]
                art_dict = {'icon': ADDON_ICON, 'thumb': entryThumb, 'poster': entryThumb}
                entryParams = None
            else:
                entryPlot = ''
                entryParams = params

            # add fanart if option is selected
            if ADDON_VIDEO_FANART:
                art_dict['fanart'] = entry_url.replace( BASEURL, IMAGES_URL + '/thumbs' ) + '.jpg'

            yield (
                build_url({'action': 'actionResolve', 'url': entry_url}),
                makeListItem(
                    unescapeHTMLText(entry_title),
                    entry_url,
                    art_dict,
                    entryPlot,
                    is_folder = False,
                    is_special = True,
                    oldParams = entryParams
                ),
                False
            )

    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_movieItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    setViewMode()

def actionRecentlyWatchedMenu(params):

    data = recently_watched_load()

    # Persistent property with item metadata.
    infoItems = getWindowProperty(PROPERTY_INFO_ITEMS) or { }

    if ADDON_SERIES_THUMBS:
        hashes = {}

        # get all hash files and combine as could be in any of them
        for path_tmp in [ URL_PATHS['dubbed'], URL_PATHS['cartoons'], URL_PATHS['subbed'] ]:
            hashes.update( hash_file_get( path_tmp ) )

    def _recentlyWatchedItemsGen():
        for title_hash, title_data in reversed(data.items()):

            entry_plot = ''

            # If there's metadata for this entry use it.
            # this is requested by the user with "Show Information".
            if title_data[ 'url' ] in infoItems:
                entry_plot, item_thumb = infoItems[title_data[ 'url' ]]
                art_dict = {'icon': ADDON_ICON, 'thumb': item_thumb, 'poster': item_thumb}
            else:

                # use default addon dict by default
                art_dict = ADDON_ICON_DICT
                if ADDON_SERIES_THUMBS:

                    img_url = title_data[ 'url' ].replace( '?season=all', '/season=all' )
                    img_url = img_url.replace( '/season=all&lang=sub', '' ).replace( '/season=all&lang=dub', '' )
                    img_url = img_url.replace( '/season=all&lang=cartoon', '' ).replace( '/season=all', '' )
                    url_hash = generate_md5( img_url )

                    if url_hash in hashes.keys():
                        thumb_from_hash = thumb_path_get( hashes.get( url_hash, '' ) )
                        art_dict = {'icon': ADDON_ICON, 'thumb': thumb_from_hash, 'poster': thumb_from_hash}

            yield (
                build_url({'action': 'actionEpisodesMenu', 'url': title_data[ 'url' ]}),
                makeListItem(title_data[ 'name' ], title_data[ 'url' ], art_dict, entry_plot, True, None, None, True),
                True
            )

    xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_recentlyWatchedItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)
    setViewMode() # Set the skin layout mode if the option is enabled.

def actionSearchMenu(params):

    """ A sub menu, lists search options. """

    def _modalKeyboard(heading):
        kb = xbmc.Keyboard('', heading)
        kb.doModal()
        return kb.getText() if kb.isConfirmed() else ''

    if 'searchType' in params:

        # Support for the 'actionShowInfo()' function reloading this route,
        # sending it an already searched query.
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
        # URL_PATHS['search'] - special, non-web path used by 'getCatalogProperty()'.
        PLUGIN_ID,
        (
            (
                build_url({
                    'action': 'actionSearchMenu',
                    'path': URL_PATHS['search'],
                    'searchType': 'series',
                    'searchTitle': __language__(30100)
                }),
                xbmcgui.ListItem('[COLOR lavender][B]' + __language__(30100) + '[/B][/COLOR]'),
                True
            ),
            (
                build_url({
                    'action': 'actionSearchMenu',
                    'path': URL_PATHS['search'],
                    'searchType': 'movies',
                    'searchTitle': __language__(30101)
                }),
                xbmcgui.ListItem('[COLOR lavender][B]' + __language__(30101) + '[/B][/COLOR]'),
                True
            ),
            (
                build_url({
                    'action': 'actionSearchMenu',
                    'path': URL_PATHS['search'],
                    'searchType': 'episodes',
                    'searchTitle': __language__(30102)
                }),
                xbmcgui.ListItem('[COLOR lavender][B]' + __language__(30102) + '[/B][/COLOR]'),
                True
            ),
            (
                build_url({'action': 'actionGenresMenu', 'path': URL_PATHS['genre']}),
                xbmcgui.ListItem('[COLOR lavender][B]' + __language__(30103) + '[/B][/COLOR]'),
                True
            ),
            (
                build_url({'action': 'actionTraktMenu', 'path': 'trakt'}),
                xbmcgui.ListItem('[COLOR lavender][B]' + __language__(30104) + '[/B][/COLOR]'),
                True
            ),
            (
                build_url({'action': 'actionSearchHistory', 'path': 'searchHistory'}),
                xbmcgui.ListItem('[COLOR lavender][B]' + __language__(30105) + '[/B][/COLOR]'),
                True
            )
        )
    )

    xbmcplugin.endOfDirectory(PLUGIN_ID)

def actionSearchHistory(params):

    """ A sub menu, lists all previous searches along with their categories. """

    # Non-UI setting, it's just a big string.
    history = ADDON.getSetting('searchHistory').split('\n')

    # A blank string split creates a list with a blank string inside
    # so test if the first item is valid.
    if history[0]:
        # Use list indexes to map to 'searchType' and a label prefix.
        historyTypeNames = ['series', 'movies', 'episodes']
        historyPrefixes = ['(Cartoon/Anime)', '(Movie)', '(Episode)']

        searchPath = URL_PATHS['search']

        historyItems = tuple(
            (
                build_url({
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
            build_url({'action': 'actionSearchHistoryClear'}), xbmcgui.ListItem('[B]Clear History...[/B]'), False
        )
        xbmcplugin.addDirectoryItems(PLUGIN_ID, (clearHistoryItem,) + historyItems)
    else:
        xbmcplugin.addDirectoryItem(PLUGIN_ID, '', xbmcgui.ListItem('(No History)'), isFolder=False)
    xbmcplugin.endOfDirectory(PLUGIN_ID)


def actionSearchHistoryClear(params):

    dialog = xbmcgui.Dialog()
    if dialog.yesno('Clear Search History', 'Are you sure?'):
        ADDON.setSetting('searchHistory', '')
        dialog.notification(PLUGIN_TITLE, 'Search history cleared', xbmcgui.NOTIFICATION_INFO, 3000, False)
        # Show the search menu afterwards.
        xbmc.executebuiltin('Container.Update(' + PLUGIN_URL + '?action=actionSearchMenu,replace)')

def actionGenresMenu(params):

    """ A sub menu, lists the genre categories in the genre search."""

    r = request_helper(BASEURL + URL_PATHS['genre'])
    html = r.text

    data_start_index = html.find( SITE_SETTINGS[ 'genre' ][ 'start' ] )
    if data_start_index == -1:
        raise Exception('Genres list scrape fail')

    xbmcplugin.addDirectoryItems(
        PLUGIN_ID,
        tuple(
            (
                build_url({
                    'action': 'actionCatalogMenu',
                    'path': '/search-by-genre/page/' + match.group(1).rsplit('/', 1)[1],
                    'searchType': 'genres'
                }),
                xbmcgui.ListItem(match.group(2)),
                True
            )
            for match in re.finditer( SITE_SETTINGS[ 'genre' ][ 'regex' ], html[data_start_index : html.find( SITE_SETTINGS[ 'genre' ][ 'end' ] )])
        )
    )
    xbmcplugin.endOfDirectory(PLUGIN_ID)

def actionRecentlyWatchedRemove(params):

    """ Removes from recently watched """

    if recently_watched_remove( params['url'] ):
        xbmcgui.Dialog().notification(
            PLUGIN_TITLE, 'Removed from recently watched', xbmcgui.NOTIFICATION_INFO, 3000, True
        )

    return

def actionRestoreDatabase(params):

    """
    Action called from the settings dialog.
    This will update all the WatchNixtoons2 'strFilename' columns of table 'files' of
    Kodi's MyVideos###.db with the new BASEURL used by the add-on so that episodes are
    still considered as watched (playcount >= 1).

    Since the domain is now being removed when being passed to the params,
    this hsould be the last time it needs to be ran
    """

    if not xbmcgui.Dialog().yesno(
        PLUGIN_TITLE,
        'This will update the Kodi database to remember any WatchNixtoons2 episodes that ' \
        'were already watched, but forgotten after an add-on update.\nProceed?',
        nolabel = 'Cancel',
        yeslabel = 'Ok'
    ):
        return

    try:
        import sqlite3
    except Exception:
        xbmcgui.Dialog().notification(
            PLUGIN_TITLE, 'sqlite3 not found', xbmcgui.NOTIFICATION_WARNING, 3000, True
        )
        return

    # Find the 'MyVideos###.db' file.
    dirs, files = xbmcvfs.listdir('special://database')
    for file in files:
        if 'MyVideos' in file and file.endswith('.db'):
            path = translate_path('special://database/' + file)
            break
    else:
        xbmcgui.Dialog().notification(
            PLUGIN_TITLE, 'MyVideos database file not found', xbmcgui.NOTIFICATION_WARNING, 3000, True
        )
        return

    # Update the database.

    OLD_DOMAINS = domains_get()

    replaceDomainFunc = lambda original, oldDomain: original.replace( 'https%3A%2F%2F' + oldDomain, '' )
    totalUpdates = 0

    try:
        connection = sqlite3.connect(path)
    except Exception as err_str:
        xbmc_debug(err_str)
        xbmcgui.Dialog().notification(
            PLUGIN_TITLE,
            'Unable to connect to MyVideos database',
            xbmcgui.NOTIFICATION_WARNING,
            3000,
            True
        )
        return

    if six.PY3:
        from functools import reduce

    getCursor = connection.cursor()
    setCursor = connection.cursor()
    pattern = PLUGIN_URL + '%actionResolve%'
    for idFile, strFilename in getCursor.execute(
        "SELECT idFile,strFilename FROM files WHERE strFilename LIKE '%s'" % pattern
    ):
        if any(oldDomain in strFilename for oldDomain in OLD_DOMAINS):
            strFilename = reduce(replaceDomainFunc, OLD_DOMAINS, strFilename)
            setCursor.execute("UPDATE files SET strFilename=? WHERE idFile=?", (strFilename, idFile))
            totalUpdates += 1

    try:
        if totalUpdates:
            # Only commit if needed.
            connection.commit()
        connection.close()
    except Exception:
        xbmcgui.Dialog().notification(
            PLUGIN_TITLE,
            'Unable to update the database (file permission error?)',
            xbmcgui.NOTIFICATION_WARNING,
            3000,
            True
        )
        return

    # Bring a notification before finishing.
    if totalUpdates:
        xbmcgui.Dialog().ok(
            PLUGIN_TITLE, 'Database update complete (%i items updated).' % totalUpdates
        )
    else:
        xbmcgui.Dialog().ok(
            PLUGIN_TITLE, 'Finished. No updates needed (0 items updated).'
        )

def actionUpdateFavourites(params):

    """
    Action called from the settings dialog.
    This will update all the Kodi favourites that use WatchNixtoons2
    so that they use the new BASEURL.
    """

    if not xbmcgui.Dialog().yesno(
        PLUGIN_TITLE,
        'This will update any of your Kodi Favourites created with older versions of ' \
        'WatchNixtoons2 so they can point to the latest web address that the add-on uses.' \
        '\nProceed?',
        nolabel = 'Cancel',
        yeslabel = 'Ok'
    ):
        return

    FAVOURITES_PATH = 'special://userdata/favourites.xml'

    file = xbmcvfs.File(FAVOURITES_PATH)
    favoritesText = file.read()
    file.close()
    originalText = favoritesText[:] # Get a backup copy of the content.

    OLD_DOMAINS = domains_get()

    replaceDomainFunc = lambda original, oldDomain: original.replace( 'https%3A%2F%2F' + oldDomain, '' )

    if any(oldDomain in originalText for oldDomain in OLD_DOMAINS):

        if six.PY3:
            from functools import reduce

        favoritesText = reduce(replaceDomainFunc, domains_get(), favoritesText)

        try:
            file = xbmcvfs.File(FAVOURITES_PATH, 'w')
            file.write(favoritesText)
            file.close()
        except Exception:
            try:
                # Try again in case this was some weird encoding error and
                # not a write-permission error.
                file = xbmcvfs.File(FAVOURITES_PATH, 'w')
                file.write(originalText)
                file.close()
                detail = ' (original was restored)'
            except Exception:
                detail = ''

            xbmcgui.Dialog().notification(
                PLUGIN_TITLE, 'Error while writing to file' + detail, xbmcgui.NOTIFICATION_WARNING, 3000, True
            )
            return

        if 'watchnixtoons2' in xbmc.getInfoLabel('Container.PluginName'):
            xbmc.executebuiltin('Dialog.Close(all)')

        xbmcgui.Dialog().ok(
            PLUGIN_TITLE,
            'One or more items updated succesfully. Kodi will now reload the Favourites file...'
        )
        # Reloads 'favourites.xml'.
        xbmc.executebuiltin('LoadProfile(%s)' % xbmc.getInfoLabel('System.ProfileName'))
    else:
        xbmcgui.Dialog().ok(PLUGIN_TITLE, 'Finished. No old favorites found.')

def actionShowSettings(params):

    # Modal dialog, so the program won't continue from this point until user closes\confirms it.
    ADDON.openSettings()

    # So right after it is a good time to update any settings globals.
    global ADDON_SHOW_CATALOG
    ADDON_SHOW_CATALOG = ADDON.getSetting('showCatalog') == 'true'

    global ADDON_LATEST_DATE
    # Set the catalog to be reloaded in case the user changed
    # the "Order 'Latest Releases' By Date" setting.
    newLatestDate = ADDON.getSetting('useLatestDate') == 'true'
    if ADDON_LATEST_DATE != newLatestDate and URL_PATHS['latest'] in getRawWindowProperty(PROPERTY_CATALOG_PATH):
        setRawWindowProperty(PROPERTY_CATALOG_PATH, '')
    ADDON_LATEST_DATE = newLatestDate

    global ADDON_LATEST_THUMBS
    ADDON_LATEST_THUMBS = ADDON.getSetting('showLatestThumbs') == 'true'

def getPageMetadata(html):

    """
    If we're on an episode or (old) movie page,
    see if there's a parent page with the actual metadata.
    """

    string_start_index = html.find( SITE_SETTINGS[ 'page_meta' ][ 'start' ] )
    if string_start_index != -1:
        parent_url = re.search( SITE_SETTINGS[ 'page_meta' ][ 'regex' ], html[string_start_index:] ).group(1)
        if '/anime/movies' not in parent_url:
            r = request_helper( ensure_full_url( BASEURL, parent_url ) )
            if r.ok:
                html = r.text

    # Thumbnail scraping.
    thumb = ''
    string_start_index = html.find( SITE_SETTINGS[ 'thumbnail' ][ 'start' ] )
    if string_start_index != -1:
        # 19 = len('og:image" content="')
        thumb = html[string_start_index+19 : html.find('"', string_start_index+19)]
        thumb = ensure_full_url( BASEURL, thumb )
        # add headers
        thumb += get_thumbnail_headers()

    if thumb:
        # animationexplore seems more reliable
        # since it now seems to be the default on the site this can be removed in the future
        thumb = thumb.replace( BASEURL + '/wp-content', IMAGES_URL )

    # The shows plot scraping.
    plot = ''
    string_start_index = html.find( SITE_SETTINGS[ 'page_plot' ][ 'start' ] )
    if string_start_index != -1:
        match = re.search( SITE_SETTINGS[ 'page_plot' ][ 'regex' ], html[string_start_index:], re.DOTALL)
        plot = unescapeHTMLText(match.group(1).strip()) if match else ''

    return plot, thumb

def actionShowInfo(params):

    xbmcgui.Dialog().notification(PLUGIN_TITLE, 'Requesting info...', ADDON_ICON, 2000, False)

    # Get the desktop page for the item, whatever it is.
    url = params['url'].replace('/m.', '/www.', 1) # Make sure the URL points to the desktop site.
    r = request_helper( ensure_full_url( BASEURL, url ) )
    html = r.text

    plot, thumb = getPageMetadata(html)

    # Use a persistent memory property holding a dictionary, and refresh the directory listing.
    if plot or thumb:
        info_items = getWindowProperty(PROPERTY_INFO_ITEMS) or { }
        info_items[url] = (plot, (thumb or 'DefaultVideo.png'))
        setWindowProperty(PROPERTY_INFO_ITEMS, info_items)
        xbmc.executebuiltin('Container.Update(%s,replace)' % (PLUGIN_URL + '?' + params['oldParams']))
    else:
        xbmcgui.Dialog().notification(PLUGIN_TITLE, 'No info found', ADDON_ICON, 1500, False)

def get_title_info(unescaped_title):

    """
    We need to interpret the full title of each episode's link's string
    for information like episode number, season and show title.
    """

    season = None
    episode = None
    multi_part = None
    show_title = unescaped_title
    episode_title = ''

    seasonIndex = unescaped_title.find('Season ') # 7 characters long.
    if seasonIndex != -1:
        season = unescaped_title[seasonIndex+7 : unescaped_title.find(' ', seasonIndex+7)]
        if not season.isdigit():
            # Handle inconsistently formatted episode title, with possibly ordinal season
            # before or after the word "Season" (case unknown, inconsistent).
            if season == 'Episode':
                # Find the word to the left of "Season ",
                # separated by spaces (spaces not included in the result).
                season = unescaped_title[unescaped_title.rfind(' ', 0, seasonIndex-1) + 1 : seasonIndex-1]
                # Include the "nth Season" term in the title.
                show_title = unescaped_title[:seasonIndex+7].strip(' -–:')
            else:
                show_title = unescaped_title[:seasonIndex].strip(' -–:')
            season = {'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5'}.get(season.lower(), '')
        else:
            show_title = unescaped_title[:seasonIndex].strip(' -–:')

    episode_index = unescaped_title.find(' Episode ') # 9 characters long.

    if episode_index != -1:
        space_index = unescaped_title.find(' ', episode_index+9)
        if space_index > episode_index:
            # For multi_part episodes, like "42-43".
            episode_split = unescaped_title[episode_index+9 : space_index].split('-')
            episode = filter(str.isdigit, episode_split[0])
            multi_part = filter(str.isdigit, episode_split[1]) if len(episode_split) > 1 else None

            # Get the episode title string (stripped of spaces, hyphens and en-dashes).
            english_index = unescaped_title.rfind(' English', space_index)
            if english_index != -1:
                episode_title = unescaped_title[space_index+1 : english_index].strip(' -–:')
            else:
                episode_title = unescaped_title[space_index+1:].strip(' -–:')
            # Safeguard for when season 1 is ocasionally omitted in the title.
            if not season:
                season = '1'

    if episode:
        return (show_title[:episode_index].strip(' -'), season, episode, multi_part, episode_title.strip(' /'))

    english_index = unescaped_title.rfind(' English')
    if english_index != -1:
        return (unescaped_title[:english_index].strip(' -'), None, None, None, '')

    return (unescaped_title.strip(' -'), None, None, None, '')

def makeListItem(title, url, art_dict, plot, is_folder, is_special, oldParams, isRecent=False):

    unescaped_title = unescapeHTMLText(title)
    plot = unescapeHTMLText(plot)
    item = xbmcgui.ListItem(unescaped_title)
    is_playable = False

    if not (is_folder or is_special):
        title, season, episode, multi_part, episode_title = get_title_info(unescaped_title)
        # Playable content.
        is_playable = True
        item_info = {
            'mediatype': 'episode' if episode else 'tvshow',
            'tvshowtitle': title,
            'title': episode_title,
            'plot': plot
        }

        if six.PY3:
            episode = str(episode)

        if episode and episode.isdigit():
            item_info['season'] = int(season) if season.isdigit() else -1
            item_info['episode'] = int(episode)

        item_set_info( item, item_info )

    elif is_special:
        is_playable = True
        item_set_info( item, {'mediatype': 'movie', 'title': unescaped_title, 'plot': plot} )
    else:
        item_set_info( item, {'mediatype': 'tvshow', 'title': unescaped_title, 'plot': plot} )

    if art_dict:
        item.setArt(art_dict)

    # Add the context menu items, if necessary.
    context_menu_list = []
    if oldParams:
        context_menu_list.append(
            (
                'Nixtoons Information',
                'RunPlugin('+PLUGIN_URL+'?action=actionShowInfo&url='+urllib_parse.quote_plus(url)+'&oldParams='+urllib_parse.quote_plus(urllib_parse.urlencode(oldParams))+')'
            )
        )

    if is_playable:
        # Allows the checkmark to be placed on watched episodes.
        item.setProperty('IsPlayable', 'true')
        # add content menu to play chapters
        context_menu_list.append(
            (
                'Play Chapters',
                'PlayMedia('+PLUGIN_URL+'?action=actionResolve&url='+urllib_parse.quote_plus(url)+'&playChapters=1)'
            )
        )
    if isRecent:
        # So item can be removed
        context_menu_list.append(
            (
                'Remove',
                'PlayMedia('+PLUGIN_URL+'?action=actionRecentlyWatchedRemove&url='+urllib_parse.quote_plus(url)+')'
            )
        )

    if context_menu_list:
        item.addContextMenuItems(context_menu_list)

    return item

def makeListItemClean(title, url, art_dict, plot, is_folder, is_special, oldParams):

    """
    Variant of the 'makeListItem()' function
    tries to format the item label using the season and episode.
    """

    unescaped_title = unescapeHTMLText(title)
    plot = unescapeHTMLText(plot)
    is_playable = False

    if is_folder or is_special:
        item = xbmcgui.ListItem(unescaped_title)
        if is_special:
            is_playable = True
            item_set_info( item, {'mediatype': 'video', 'title': unescaped_title} )
    else:
        title, season, episode, multi_part, episode_title = get_title_info(unescaped_title)

        # dirty way to ensure is a string
        # this is due to filters being used, todo for clean-up
        if six.PY3:
            if episode:
                episode = "".join(episode)
            if season:
                season = "".join(season)
            if multi_part:
                multi_part = "".join(multi_part)

        if episode and episode.isdigit():
            # The clean episode label will have this format:
            # "SxEE Episode Name", with S and EE standing for digits.
            item = xbmcgui.ListItem(
                '[B]' + season + 'x' + episode.zfill(2) + ('-' + multi_part if multi_part else '') + '[/B] '
                + (episode_title or title)
            )
            item_info = {
                'mediatype': 'episode',
                'tvshowtitle': title,
                'title': title,
                'plot': plot,
                'season': int(season) if season.isdigit() else -1,
                'episode': int(episode)
            }
        else:
            item = xbmcgui.ListItem(title)
            item_info = {
                'mediatype': 'tvshow',
                'tvshowtitle': title,
                'title': title,
                'plot': plot
            }
        item_set_info( item, item_info )
        is_playable = True

    if art_dict:
        item.setArt(art_dict)

    # Add the context menu items, if necessary.
    context_menu_list = []
    if oldParams:
        context_menu_list.append(
            (
                'Show Information',
                'RunPlugin('+PLUGIN_URL+'?action=actionShowInfo&url='+urllib_parse.quote_plus(url)+'&oldParams='+urllib_parse.quote_plus(urllib_parse.urlencode(oldParams))+')'
            )
        )
    if is_playable:
        # Allows the checkmark to be placed on watched episodes.
        item.setProperty('IsPlayable', 'true')
        # add content menu to play chapters
        context_menu_list.append(
            (
                'Play Chapters',
                'PlayMedia('+PLUGIN_URL+'?action=actionResolve&url='+urllib_parse.quote_plus(url)+'&playChapters=1)'
            )
        )

    if context_menu_list:
        item.addContextMenuItems(context_menu_list)

    return item

def catalogFromIterable(iterable):

    """
    Manually sorts items from an iterable into an alphabetised catalog.
    Iterable contains (URL, name) pairs that might refer to a series, episode, ova or movie.
    """

    catalog = {key: [ ] for key in ascii_uppercase}
    misc_section = catalog['#'] = [ ]
    for item in iterable:
        key = item[1][0].upper()
        if key in catalog:
            catalog[key].append(item)
        else:
            misc_section.append(item)
    return catalog

def makeLatestCatalog(params):

    """ Returns a list of links from the 'Latest 50 Releases' area """

    html = request_helper(BASEURL + SITE_SETTINGS[ 'latest' ][ 'url' ]).text

    data_start_index = html.find( SITE_SETTINGS[ 'latest' ][ 'start' ] )
    if data_start_index == -1:
        raise Exception('Latest catalog scrape fail')

    if ADDON_LATEST_DATE:
        # Make the catalog dict only have a single section, "LATEST", with items listed as they are.
        # This way the actionCatalogMenu() function will show this single section directly,
        # with no alphabet categories.
        return {
            'LATEST': tuple(
                (match.group('link'), match.group('name'), ensure_url_schema(match.group('img')))
                for match in re.finditer(
                    SITE_SETTINGS[ 'latest' ][ 'regex' ], html[data_start_index : html.find( SITE_SETTINGS[ 'latest' ][ 'end' ], data_start_index )]
                )
            )
        }

    return catalogFromIterable(
        (match.group('link'), match.group('name'), ensure_url_schema(match.group('img')))
        for match in re.finditer(
            SITE_SETTINGS[ 'latest' ][ 'regex' ], html[data_start_index : html.find( SITE_SETTINGS[ 'latest' ][ 'end' ], data_start_index )]
        )
    )

def makePopularCatalog(params):

    """ Scrape from the sidebar content on the homepage to get popular list """

    html = request_helper(BASEURL).text

    data_start_index = html.find( SITE_SETTINGS[ 'popular' ][ 'start' ] )
    if data_start_index == -1:
        raise Exception('Popular catalog scrape fail: ' + params['path'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            SITE_SETTINGS[ 'popular' ][ 'regex' ], html[data_start_index : html.find( SITE_SETTINGS[ 'popular' ][ 'end' ], data_start_index )]
        )
    )

def makeSeriesSearchCatalog(params):

    html = request_helper(
        BASEURL + '/search',
        data={'catara': params['query'], 'konuara': 'series'},
        extra_headers={'Referer': BASEURL + '/'}
    ).text

    data_start_index = html.find( SITE_SETTINGS[ 'series_search' ][ 'start' ] )
    if data_start_index == -1:
        raise Exception('Series search scrape fail: ' + params['query'])

    return catalogFromIterable(
        (match.group('link'), match.group('name'), match.group('img'))
        for match in re.finditer(
            SITE_SETTINGS[ 'series_search' ][ 'regex' ],
            html[data_start_index : html.find( SITE_SETTINGS[ 'series_search' ][ 'end' ] , data_start_index)]
        )
    )

def makeMoviesSearchCatalog(params):

    """ Tries a movie category search (same code as in 'makeGenericCatalog()'). """

    html = request_helper(BASEURL + URL_PATHS['movies']).text

    data_start_index = html.find('"ddmcc"')
    if data_start_index == -1:
        raise Exception('Movies search scrape fail: ' + params['query'])

    query_lower = params['query'].lower()

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            '''<a href="([^"]+).*?>([^<]+)''', html[data_start_index : html.find('/ul></ul', data_start_index)]
        )
        if query_lower in match.group(2).lower()
    )

def makeEpisodesSearchCatalog(params):

    html = request_helper(
        BASEURL + '/search',
        data={'catara': params['query'], 'konuara': 'episodes'},
        extra_headers={'Referer': BASEURL+'/'}
    ).text

    data_start_index = html.find( SITE_SETTINGS[ 'episode_search' ][ 'start' ] )
    if data_start_index == -1:
        raise Exception('Episode search scrape fail: ' + params['query'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            SITE_SETTINGS[ 'episode_search' ][ 'regex' ],
            html[data_start_index : html.find( SITE_SETTINGS[ 'episode_search' ][ 'end' ] , data_start_index )],
            re.DOTALL
        )
    )

def makeSearchCatalog(params):
    search_type = params.get('searchType', 'series')
    if search_type == 'series':
        return makeSeriesSearchCatalog(params)
    if search_type == 'movies':
        return makeMoviesSearchCatalog(params)
    return makeEpisodesSearchCatalog(params)

def makeGenericCatalog(params):

    """ makes list for generic scrape, e.g. dubbed anime list """

    html = request_helper(BASEURL + params['path']).text

    data_start_index = html.find( SITE_SETTINGS[ 'catalog' ][ 'start' ] )

    # have another attempt
    if data_start_index == -1 and SITE_SETTINGS[ 'catalog' ][ 'start_alt' ] is not False:
        data_start_index = html.find( SITE_SETTINGS[ 'catalog' ][ 'start_alt' ] )

    if data_start_index == -1:
        raise Exception('Generic catalog scrape fail: ' + params['path'])

    return catalogFromIterable(
        match.groups()
        for match in re.finditer(
            SITE_SETTINGS[ 'catalog' ][ 'regex' ],
            html[data_start_index : html.find( SITE_SETTINGS[ 'catalog' ][ 'end' ], data_start_index )]
        )
    )

def getCatalogProperty(params):

    """
    Retrieves the catalog from a persistent XBMC window property between different add-on
    directories, or recreates the catalog based on one of the catalog functions.
    """

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
    current_path = getRawWindowProperty(PROPERTY_CATALOG_PATH)
    if (
        # If we're coming in from a search and the search query and type are different,
        # or if we're not coming in from a search and the paths are simply different,
        # rebuild the catalog.
        ('query' in params and (params['query'] not in current_path or params['searchType'] not in current_path))
        or ('query' not in params and current_path != path)
    ):
        catalog = _rebuildCatalog()
    else:
        catalog = getWindowProperty(PROPERTY_CATALOG)
        if not catalog:
            catalog = _rebuildCatalog()
    return catalog

def get_parent_page(html):

    """ Retrieves parent page's name and url """

    string_start_index = html.find( SITE_SETTINGS[ 'parent' ][ 'start' ] )
    match = re.search( SITE_SETTINGS[ 'parent' ][ 'regex' ], html[string_start_index:], re.DOTALL )
    url = match.group(1).strip() if match else ''
    name = unescapeHTMLText(match.group(2).strip()) if match else ''

    return { 'name': name, 'url': url }

def actionResolve(params):

    """ resolves video URL from site URL """

    urls = {
        'page': ensure_current_domain( params['url'], BASEDOMAIN, domains_get() ),
        'embed': None,
        'stream': None,
        'media': None,
        'backup': None,
        'source': [],
    }

    flags = {
        'redirect': True,
        'm3u8': False,
    }

    r = request_helper( urls['page'] )
    content = r.content

    if six.PY3:
        content = content.decode('utf-8')

    # get data & mark as recently watched
    parent = get_parent_page( content )
    recently_watched_add( parent['name'], parent['url'] )

    def _decodeSource(subContent):

        if six.PY3:
            subContent = str(subContent)

        try:
            return_url = re.search(r'src="([^"]+)', subContent).group(1)
            return ensure_full_url( BASEURL, return_url )
        except Exception:
            # Probably a temporary block, or change in embedded code.
            return None

    html = ''

    # check if is a premium only video
    if 'This Video is For the WCO Premium Users Only' in content:

        xbmc_debug( 'Premium video detected, attempting to work around for domain: ' + BASEURL )
        # check if there is a premium workaround in the site class
        is_premium = premium_workaround_check( content, urls )

        if is_premium is False:
            xbmc_debug( 'Premium video workaround failed' )
            # Notify about premium only video
            xbmcgui.Dialog().ok(
                PLUGIN_TITLE + ' Fail',
                'The video has been marked as "only for premium users".'
            )
            return

        xbmc_debug( 'Premium video workaround success' )
        urls = is_premium
        html = content

    # On rare cases an episode might have several "chapters", which are video players on the page.
    elif 'playChapters' in params or ADDON.getSetting('chapterEpisodes') == 'true':

        # try and get chapters from site class
        data_indices = re.compile( SITE_SETTINGS[ 'chapter' ][ 'regex' ], re.MULTILINE ).findall(content)

        # If more than one "urls['embed']" statement found
        # make a selection dialog and call them "chapters".
        if len(data_indices) > 1:
            selected_index = xbmcgui.Dialog().select(
                'Select Chapter', ['Chapter '+str(n) for n in xrange(1, len(data_indices)+1)]
            )
        else:
            selected_index = 0

        if selected_index != -1:
            urls['embed'] = data_indices[selected_index]
            # check site class if required to be decoded
            if DECODE_SOURCE_REQUIRED:
                urls['embed'] = _decodeSource(urls['embed'])
        else:
            # User cancelled the chapter selection.
            return

    elif 'uploads0" src=' in content:

        urls['embed'] = re.search(r'<iframe\s*id=\"(?:[a-zA-Z]+)uploads(?:[0-9]+)\"\s*src=\"([^\"]+)\"', content, re.DOTALL).group(1)

    elif '-js-0" src=' in content:

        urls['embed'] = re.search(r'<iframe\s*(?:rel=\"nofollow\")?\s*id=\"(?:[a-zA-Z]+)\-js\-(?:[0-9]+)\"\s*src=\"([^\"]+)\"', content, re.DOTALL).group(1)

    # method for .m3u8
    elif '"vjs_iframe"' in content:

        xbmc_debug( 'm3u8 Detected' )
        urls['embed'] = re.search(r'<iframe id=\"(?:[a-zA-Z0-9-]+)\" class=\"vjs_iframe\" rel=\"nofollow\" src=\"([^\"]+)\"', content, re.DOTALL).group(1)
        flags['m3u8'] = True

    else:

        embed_url_pattern = r'onclick="myFunction'
        embed_url_index = content.find(embed_url_pattern)

        # back-up search index
        if embed_url_index <= 0:
            embed_url_pattern = r'class="episode-descp"'
            embed_url_index = content.find(embed_url_pattern)
        # Normal / single-chapter episode.
        urls['embed'] = _decodeSource(content[embed_url_index:])
        # User asked to play multiple chapters, but only one chapter/video player found.
        if urls['embed'] and 'playChapters' in params:
            xbmcgui.Dialog().notification(PLUGIN_TITLE, 'Only 1 chapter found...', ADDON_ICON, 2000, False)

    # Notify a failure in solving the player obfuscation.
    if not urls['embed'] and not urls['stream']:
        xbmcgui.Dialog().ok(PLUGIN_TITLE, 'Unable to find a playable source')
        return

    if not urls['stream']:

        if 'inc/embed/index.php' in urls['embed']:
            urls['embed'] = urls['embed'].replace( 'inc/embed/index.php', 'inc/embed/video-js.php' )

        # Request the embedded player page.
        r2 = request_helper(
            # Sometimes a '&#038;' symbol is present in this URL.
            unescapeHTMLText(urls['embed']),
            data = None,
            extra_headers = {
                'Referer': urls['embed'],
            }
        )
        html = r2.text

    # Notify about temporary blocks / failures.
    if 'high volume of requests' in html:
        xbmcgui.Dialog().ok(
            PLUGIN_TITLE + ' Fail (Server Response)',
            '"We are getting extremely high volume of requests on our video servers ' \
            'so that we temporarily block for free videos for free users.' \
            'I apologize for the inconvenience."'
        )
        return

    # Find the stream URLs.
    if 'getvid?evid' in html:

        if 'getRedirectedUrl(videoUrl)' in html:
            source_url =  re.search(r'\$\.getJSON\(\"([^\"]+)\"', html, re.DOTALL).group(1)
            source_url = "https://embed.wcostream.com/" + source_url + "&json"
        else:
            source_url = re.search(r'"(/inc/embed/getvidlink[^"]+)', html, re.DOTALL).group(1)
            source_url = BASEURL + source_url

        r3 = request_helper(
            source_url,
            data = None,
            extra_headers = {
                'Accept': '*/*',
                'Referer': urls['embed'],
                'X-Requested-With': 'XMLHttpRequest',
            }
        )

        if not r3.ok:
            raise Exception('Sources XMLHttpRequest request failed')

        json_data = r3.json()

        # Three qualities can be available: 480p ("SD") / 720p ("HD") / 1080p ("FHD")
        token_sd = json_data.get('enc', '')
        token_hd = json_data.get('hd', '')
        token_fhd = json_data.get('fhd', '')

        source_base_url = json_data.get('server', '') + '/getvid?evid='
        if token_sd:
            # Order the items as (LABEL, URL).
            urls['source'].append((quality_label(480), source_base_url + token_sd))
        if token_hd:
            urls['source'].append((quality_label(720), source_base_url + token_hd))
        if token_fhd:
            urls['source'].append((quality_label(1080), source_base_url + token_fhd))

        # Use the same backup stream method as the source: cdn domain + SD stream.
        urls['backup'] = json_data.get('cdn', '') + '/getvid?evid=' + (token_sd or token_hd or token_fhd)
    elif urls['stream']:
        urls['source'].append((quality_label(480), urls['stream']))
    elif flags['m3u8']:
        m3u8_url = re.search(r'<source\s*src=\"([^\"]+)\"', html, re.DOTALL).group(1)
        urls['source'].append((quality_label(1080), m3u8_url))
        flags['redirect'] = False
    elif 'getRedirectedUrl("' in html:
        m3u8_url =  re.search(r'getRedirectedUrl\(\"([^\"]+)', html, re.DOTALL).group(1)
        urls['source'].append((quality_label(1080), m3u8_url))
        flags['redirect'] = False
        flags['m3u8'] = True
    else:
        # Alternative video player page, with plain stream links in the JWPlayer javascript.
        sources_block = re.search(r'sources:\s*?\[(.*?)\]', html, re.DOTALL).group(1)
        stream_pattern = re.compile(r'\{\s*?file:\s*?"(.*?)"(?:,\s*?label:\s*?"(.*?)")?')
        urls['source'] = [
            # Order the items as (LABEL (or empty string), URL).
            (sourceMatch.group(2), sourceMatch.group(1))
            for sourceMatch in stream_pattern.finditer(sources_block)
        ]
        # Use the backup link in the 'onError' handler of the 'jw' player.
        backup_match = stream_pattern.search(html[html.find(b'jw.onError'):])
        urls['backup'] = backup_match.group(1) if backup_match else ''

    # source select
    if len(urls['source']) == 1:
        # Only one quality available.
        urls['media'] = urls['source'][0][1]
    elif len(urls['source']) > 0:
        # Always force "select quality" for now.
        if PLAYBACK_METHOD == '0':
            # Select quality.
            selected_index = xbmcgui.Dialog().select(
                'Select Quality', [(sourceItem[0] or '?') for sourceItem in urls['source']]
            )
            if selected_index != -1:
                urls['media'] = urls['source'][selected_index][1]
        else:
            # Auto-play user choice.
            urls['media'] = urls['source'][-1][1] if PLAYBACK_METHOD == '1' else urls['source'][0][1]

    if urls['media']:

        # Kodi headers for playing web streamed media.
        global MEDIA_HEADERS
        if not MEDIA_HEADERS:
            MEDIA_HEADERS = {
                'User-Agent': WNT2_USER_AGENT,
                'Accept': 'video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5',
            }

        media_head = False
        if flags['redirect']:
            # Try to un-redirect the chosen media URL.
            # If it fails, try to un-resolve the backup URL.
            # If not even the backup URL is working, abort playing.
            media_head = solve_media_redirect(urls['media'], MEDIA_HEADERS)
            if not media_head and urls['backup']:
                media_head = solve_media_redirect(urls['backup'], MEDIA_HEADERS)
            if not media_head:
                return xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())
            urls['stream'] = media_head.url
        else :
            urls['stream'] = urls['media']

        # Enforce the add-on debug setting to use HTTP access on the stream.
        if ADDON.getSetting('useHTTP') == 'true':
            # This is now being used for the fact that sometimes the SSL certificate
            # is sometimes not renewed on the media servers
            urls['stream'] = urls['stream'].replace('https://', 'http://', 1)

        # Need to use the exact same ListItem name & infolabels when playing
        # or else Kodi replaces that item in the UI listing.
        item = xbmcgui.ListItem(xbmc.getInfoLabel('ListItem.Label'))

        if flags['m3u8']:

            item.setPath(urls['stream'])

            # Disable Kodi's MIME-type request, since we already know what it is.
            item.setContentLookup(False)
            item.setMimeType('application/x-mpegURL')

            if KODI_VERSION < 19:
                item.setProperty('inputstreamaddon', 'inputstream.adaptive')
            else:
                item.setProperty('inputstream', 'inputstream.adaptive')

            item.setProperty('inputstream.adaptive.stream_headers', '&'.join(key+'='+urllib_parse.quote_plus(val) for key, val in MEDIA_HEADERS.items()))
            item.setProperty('inputstream.adaptive.stream_params', '&'.join(key+'='+urllib_parse.quote_plus(val) for key, val in MEDIA_HEADERS.items()))
            item.setProperty('inputstream.adaptive.manifest_headers', '&'.join(key+'='+urllib_parse.quote_plus(val) for key, val in MEDIA_HEADERS.items()))

            if KODI_VERSION < 22:
                item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            item.setProperty('inputstream.adaptive.original_audio_language', 'en')

            if PLAYBACK_METHOD == '0':
                item.setProperty('inputstream.adaptive.stream_selection_type', 'ask-quality')
            else:
                item.setProperty('inputstream.adaptive.stream_selection_type', 'adaptive')
            #item.setProperty('inputstream.adaptive.config', '{"ssl_verify_peer":false}')
        else:

            MEDIA_HEADERS[ 'Referer' ] = BASEURL + '/'

            item.setPath(urls['stream'] + '|' + '&'.join(key+'='+urllib_parse.quote_plus(val) for key, val in MEDIA_HEADERS.items()))
            if media_head:
                # Disable Kodi's MIME-type request, since we already know what it is.
                item.setContentLookup(False)
                item.setMimeType(media_head.headers.get('Content-Type', 'video/mp4'))

        # When coming in from a Favourite item, there will be no metadata.
        # Try to get at least a title.
        item_title = xbmc.getInfoLabel('ListItem.Title')
        if not item_title:
            match = re.search(r'<h1[^>]+>([^<]+)</h1', content)
            if match:
                if six.PY3:
                    item_title = str(match.group(1)).replace(' English Subbed', '', 1) \
                    .replace( 'English Dubbed', '', 1)
                else:
                    item_title = match.group(1).replace(' English Subbed', '', 1) \
                    .replace( 'English Dubbed', '', 1)
            else:
                item_title = ''

        episode_string = xbmc.getInfoLabel('ListItem.Episode')
        if episode_string not in ( '', '-1' ):
            season_info_label = xbmc.getInfoLabel('ListItem.Season')
            item_info = {
                'tvshowtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
                'title': unescapeHTMLText(item_title),
                'season': int(season_info_label) if season_info_label.isdigit() else -1,
                'episode': int(episode_string),
                'plot': xbmc.getInfoLabel('ListItem.Plot'),
                'mediatype': 'episode',
            }
        else:
            item_info = {
                'title': unescapeHTMLText(item_title),
                'plot': xbmc.getInfoLabel('ListItem.Plot'),
                'mediatype': 'movie',
            }

        item_set_info( item, item_info )


        # xbmc.Player().play(listitem=item)
        # Alternative play method, lets you extend the Player class with your own.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, True, item)

    else:
        # Failed. No source found, or the user didn't select one from the dialog.
        xbmcplugin.setResolvedUrl(PLUGIN_ID, False, xbmcgui.ListItem())

def get_thumbnail_headers():

    """ Thumbnail HTTP headers for Kodi to use when grabbing thumbnail images. """

    # Original code:
    #return (
    #    '|User-Agent='+urllib_parse.quote_plus(WNT2_USER_AGENT)
    #    + '&Accept='+urllib_parse.quote_plus('image/webp,*/*')
    #    + '&Referer='+urllib_parse.quote_plus(BASEURL+'/')
    #)

    cookie_property = getRawWindowProperty(PROPERTY_SESSION_COOKIE)
    cookies = ('&Cookie=' + urllib_parse.quote_plus(cookie_property)) if cookie_property else ''

    # Since it's a constant value, it can be precomputed.
    return '|User-Agent=' + urllib_parse.quote_plus(WNT2_USER_AGENT) + \
        '&Accept=image%2Fwebp%2C%2A%2F%2A&Referer=' + \
        urllib_parse.quote_plus(BASEURL+'/') + cookies

def domains_get():

    """ Returns possible domains, in the order of likeliness. """

    return (
        'www.wcostream.tv',
        'www.wcoflix.tv',
        'www.wcoforever.net',
        'www.wcofun.net',
        'www.wcofun.tv',
        'www.wcofun.org',
        'www.wcofun.com',
        'www.wcostream.com',
        'm.wcostream.com',
        'www.watchcartoononline.io',
        'm.watchcartoononline.io',
        'www.thewatchcartoononline.tv'
    )

def thumb_path_get( thumb_id ):

    if thumb_id:
        if thumb_id.startswith( 'tm-' ):
            return TMDB_IMAGES_URL + '/t/p/w500/' + thumb_id.replace( 'tm-', '' ) + '.jpg'
        return IMAGES_URL + '/catimg/' + thumb_id + '.jpg' + get_thumbnail_headers()
    
    return ''

def solve_media_redirect(url, headers):

    """
    Use (streamed, headers-only) GET requests to fulfill possible 3xx redirections.
    Returns the (headers-only) final response, or None.
    """

    while True:
        try:
            media_head = rqs_get().get(
                url, stream=True, headers=headers, allow_redirects=False, verify=False, timeout=10
            )
            if 'Location' in media_head.headers:
                url = media_head.headers['Location'] # Change the URL to the redirected location.
            else:
                media_head.raise_for_status()
                return media_head # Return the response.
        except Exception:
            return None # Return nothing on failure.

# Defined after all the functions exist.
CATALOG_FUNCS = {
    URL_PATHS['latest']: makeLatestCatalog,
    URL_PATHS['popular']: makePopularCatalog,
    URL_PATHS['search']: makeSearchCatalog
}

def main():

    """ Main add-on routing function, calls a certain action (function) """

    # The 'action' parameter is the direct name of the function.
    params = dict(urllib_parse.parse_qsl(sys.argv[2][1:], keep_blank_values=True))
    # Defaults to 'actionMenu()'.
    globals()[params.get('action', 'actionMenu')](params)
