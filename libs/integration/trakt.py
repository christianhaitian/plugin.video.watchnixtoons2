# -*- coding: utf-8 -*-
import requests
import xbmcgui
from xbmc import sleep

class SimpleTrakt():

    TRAKT_API_URL = 'https://api.trakt.tv'

    CLIENT_ID = 'fd584905ac39b30b8458d583b75ea1b39743e036b293da91c838fdc3cc59dbcc'
    CLIENT_SECRET = 'd9fa7c625add7a6df29be40b9364482a8c61f520df9961a6708742b79c3b3afe'

    _INSTANCE = None

    @classmethod
    def getInstance(cls):

        if not cls._INSTANCE:
            cls._INSTANCE = SimpleTrakt()
        return cls._INSTANCE

    @classmethod
    def clearTokens(cls, addon):

        cleared = False
        access_token = addon.getSetting('trakt_access')
        if access_token:
            requests.post(
                cls.TRAKT_API_URL + '/oauth/revoke',
                json = {
                    'access_token': access_token,
                    'client_id': cls.CLIENT_ID,
                    'client_secret': cls.CLIENT_SECRET
                },
                timeout = 10
            )
            cleared = True
        addon.setSetting('trakt_access', '')
        addon.setSetting('trakt_refresh', '')
        return cleared

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                'Content-Type': 'application/json',
                'trakt-api-key': self.CLIENT_ID,
                'trakt-api-version': '2',
            }
        )

    def ensureAuthorized(self, addon):

        access_token = addon.getSetting('trakt_access')
        if not access_token:
            tokens = self._tryPairDialog()
            if tokens:
                access_token, refresh_token = tokens
                addon.setSetting('trakt_access', access_token)
                addon.setSetting('trakt_refresh', refresh_token)

        if access_token:
            self.session.headers.update({'Authorization': 'Bearer ' + access_token})
            return True
        return False

    def getUserLists(self, addon):

        r1 = self._traktRequest('/users/me/lists', data=None, addon=addon)
        r2 = self._traktRequest('/users/likes/lists', data=None, addon=addon)

        def _traktDataGen(*iterables):
            for suffix, lists in iterables:
                for list in lists:
                    yield (
                        list['name'] + suffix,
                        '/users/%s/lists/%i' % (list['user']['ids']['slug'], list['ids']['trakt']),
                        list['description']
                    )

        return _traktDataGen(
            ('', (r1.json() if r1.ok else ())),
            (' (Liked)', ((item['list'] for item in r2.json()) if r2.ok else ()))
        )

    def getListItems(self, listURL, addon):

        # This query ignores 'person' type objects, like actors.
        r = self._traktRequest(listURL + '/items/movie,show,season,episode?extended=full', data=None, addon=addon)

        def _preprocessItemsGen(iterable):
            searchTypes = {'movie': 'movies', 'show': 'series', 'season': 'series', 'episode': 'series'}
            for item in iterable:
                itemType = item['type']
                itemProps = item[itemType]

                if itemType == 'season':
                    # Since we can't point to a specific season, point to the show instead.
                    label = itemProps['title'] + ' (' + item['show']['title'] + ')'
                    query = item['show']['title']
                    overview = itemProps['overview'] if itemProps['overview'] else item['show']['overview']
                elif itemType == 'episode':
                    label = itemProps['title'] + ' (Season %i) (%s)' % (itemProps['season'], item['show']['title'])
                    query = item['show']['title']
                    overview = itemProps['overview']
                else:
                    query = label = itemProps['title']
                    overview = itemProps['overview']
                yield label, overview, searchTypes[itemType], query

        if r.ok:
            return _preprocessItemsGen(r.json())

        return ()

    def _tryPairDialog(self):

        r = self._traktRequest('/oauth/device/code', {'client_id': self.CLIENT_ID})
        if r.ok:
            json_data = r.json()
            device_code = json_data['device_code']
            total_time = json_data['expires_in']
            interval = json_data['interval']

            progress_dialog = xbmcgui.DialogProgress()
            progress_dialog.create(
                'Trakt Activation',
                'Go to [B]' + json_data['verification_url'] \
                    + '[/B] and enter this code:[COLOR aquamarine][B]' \
                    + json_data['user_code'] + '[/B][/COLOR] Time left:'
            )

            poll_data = {
                'code': device_code,
                'client_id': self.CLIENT_ID,
                'client_secret': self.CLIENT_SECRET
            }

            for s in range(total_time):
                if progress_dialog.iscanceled():
                    break
                percentage = int(s / float(total_time) * 100.0)
                progress_dialog.update(
                    percentage, 'Go to [B]' + json_data['verification_url'] + \
                    '[/B] and enter this code:[COLOR aquamarine][B]' + json_data['user_code'] + \
                    '[/B][/COLOR] Time left: [B]' + str(total_time - s) + '[/B] seconds'
                )

                if not (s % interval):
                    r2 = self._traktRequest('/oauth/device/token', poll_data)

                    if r2.status_code == 200: # Process complete.
                        progress_dialog.close()
                        json_data = r2.json()
                        return json_data['access_token'], json_data['refresh_token']

                    if r2.status_code in ( 409, 418 ):
                        progress_dialog.close()
                        break
                sleep(1000)
            else:
                progress_dialog.close()
            return None

        self._notification('Watchnixtoons2', 'Trakt request failed', useSound=True, isError=True)

        return None

    def _tryRefreshToken(self, addon):

        refresh_token = addon.getSetting('trakt_refresh')
        if refresh_token:
            r = self.session.post(
                '/oauth/token',
                json = {
                    'client_id': self.CLIENT_ID,
                    'client_secret': self.CLIENT_SECRET,
                    'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token
                },
                timeout = 10
            )
            if r.ok:
                json_data = r.json()
                addon.setSetting('trakt_access', json_data['access_token'])
                # The refresh token also gets updated
                addon.setSetting('trakt_refresh', json_data['refresh_token'])
                self.session.headers.update({'Authorization': 'Bearer ' + json_data['access_token']})
                return True

        return False

    def _traktRequest(self, path, data, addon=None):

        try:
            if data:
                r = self.session.post(self.TRAKT_API_URL + path, json=data, timeout=10)
            else:
                r = self.session.get(self.TRAKT_API_URL + path, timeout=10)

            # See if the token has expired (happens every 3 months).
            if addon and r.status_code in (401, 400, 403) and self._tryRefreshToken(addon):
                # Try once more after refreshing the token.
                r = self._traktRequest(path, data)
            return r
        except Exception:
            return type('FailedResponse', (object,), {'ok': False, 'status_code': 400})

    def _notification(self, heading, caption, useSound=False, isError=False):
        icon = xbmcgui.NOTIFICATION_ERROR if isError else xbmcgui.NOTIFICATION_INFO
        xbmcgui.Dialog().notification(heading, caption, icon, 3000, useSound)
