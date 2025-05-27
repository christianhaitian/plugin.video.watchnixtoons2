import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon


from lib.constants import ADDON, PLUGIN_ID, PLUGIN_TITLE, RESOURCE_URL, URL_PATHS
from lib.common import item_set_info, build_url

from lib.integration.trakt import SimpleTrakt

TRAKT_ICON = RESOURCE_URL + 'media/trakt_icon.png'

TRAKT_ART_DICT = {
    'icon': TRAKT_ICON,
    'thumb': TRAKT_ICON,
    'poster': TRAKT_ICON,
}

def actionTraktMenu(params):

    instance = SimpleTrakt.getInstance()
    if instance.ensureAuthorized(ADDON):

        def _traktMenuItemsGen():

            for list_name, list_url, list_description in instance.getUserLists(ADDON):
                item = xbmcgui.ListItem(list_name)
                item.setArt(TRAKT_ART_DICT)
                item_set_info( item, {'title': list_name, 'plot': list_description} )
                yield (
                    build_url({'action': 'actionTraktList', 'listURL': list_url}),
                    item,
                    True
                )

        xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_traktMenuItemsGen()))
        # Only finish the directory if the user is authorized it.
        xbmcplugin.endOfDirectory(PLUGIN_ID)

def actionTraktList(params):

    """ get Trakt list """

    instance = SimpleTrakt.getInstance()
    if instance.ensureAuthorized(ADDON):

        def _traktListItemsGen():

            for item_name, overview, search_type, query in sorted(instance.getListItems(params['listURL'], ADDON)):

                item = xbmcgui.ListItem(item_name)
                item_set_info( item, {'title': item_name, 'plot': overview} )
                item.setArt(TRAKT_ART_DICT)
                yield (
                    # Trakt items will lead straight to a show name search.
                    build_url({
                        'action': 'actionCatalogMenu',
                        'path': URL_PATHS['search'],
                        'query': query,
                        'searchType': search_type,
                    }),
                    item,
                    True
                )

        xbmcplugin.addDirectoryItems(PLUGIN_ID, tuple(_traktListItemsGen()))
    xbmcplugin.endOfDirectory(PLUGIN_ID)

def actionTraktAbout(params):

    """ Shows about dialog to user """

    xbmcgui.Dialog().ok(
        PLUGIN_TITLE,
        'To search for items in your Trakt lists in WNT2, ' \
        'go to [B]Search > Search by Trakt List[/B] and pair your account. ' \
        'Searching for an item this way does a name search, ' \
        'same as if you went and searched for that name manually.'
    )


def actionClearTrakt(params):

    """ Clears Trakt's tokens """

    if 'watchnixtoons2' in xbmc.getInfoLabel('Container.PluginName'):
        xbmc.executebuiltin('Dialog.Close(all)')

    # Kinda buggy behavior.
    # Need to wait a bit and recreate the xbmcaddon.Addon() reference,
    # otherwise the settings don't seem to be changed.
    # See https://forum.kodi.tv/showthread.php?tid=290353&pid=2425543#pid2425543

    global ADDON
    xbmc.sleep(500)

    if SimpleTrakt.clearTokens(ADDON):
        notification_str = 'Trakt tokens cleared'
    else:
        notification_str = 'Trakt tokens already cleared'

    xbmcgui.Dialog().notification(
        PLUGIN_TITLE, notification_str, xbmcgui.NOTIFICATION_INFO, 3000, False
    )

    ADDON = xbmcaddon.Addon()
