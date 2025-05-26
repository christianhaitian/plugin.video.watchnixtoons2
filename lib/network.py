# -*- coding: utf-8 -*-
import ssl
from time import time, sleep

import requests

from six.moves import urllib_parse

from lib.constants import WNT2_USER_AGENT, BASEURL, PROPERTY_SESSION_COOKIE
from lib.common import *

# Disable urllib3's "InsecureRequestWarning: Unverified HTTPS request is being made" warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from urllib3.poolmanager import PoolManager
from requests.adapters import HTTPAdapter


class TLS11HttpAdapter(HTTPAdapter):

    """Transport adapter" that allows us to use TLSv1.1"""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_version=ssl.PROTOCOL_TLSv1_1
        )


class TLS12HttpAdapter(HTTPAdapter):

    """Transport adapter" that allows us to use TLSv1.2"""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_version=ssl.PROTOCOL_TLSv1_2
        )

rqs = requests.session()
tls_adapters = [TLS12HttpAdapter(), TLS11HttpAdapter()]

def rqs_get():

    """ returns requests.session() """

    return rqs

def request_helper(url, data=None, extra_headers=None):

    """ makes call to get/post website """

    my_headers = {
        'User-Agent': WNT2_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Cache-Control': 'no-cache',
    }

    if extra_headers:
        my_headers.update(extra_headers)

    # At the moment it's a single response cookie, "__cfduid".
    # Other cookies are set w/ Javascript by ads.
    cookie_property = getRawWindowProperty(PROPERTY_SESSION_COOKIE)
    if cookie_property:
        cookie_dict = dict(pair.split('=') for pair in cookie_property.split('; '))
    else:
        cookie_dict = None

    uri = urllib_parse.urlparse(url)
    domain = uri.scheme + '://' + uri.netloc

    start_time = time()

    status = 0
    i = 0
    while status != 200 and i < 2:
        if data:
            response = rqs.post(
                url, data=data, headers=my_headers, verify=False, cookies=cookie_dict, timeout=10
            )
        else:
            response = rqs.get(
                url, headers=my_headers, verify=False, cookies=cookie_dict, timeout=10
            )

        status = response.status_code
        if status != 200:
            if status == 403 and response.headers.get('server', '') == 'cloudflare':
                rqs.mount(domain, tls_adapters[i])
            i += 1

    # Store the session cookie(s), if any.
    if not cookie_property and response.cookies:
        setRawWindowProperty(
            PROPERTY_SESSION_COOKIE,
            '; '.join(pair[0]+'='+pair[1] for pair in response.cookies.get_dict().items())
        )

    elapsed = time() - start_time
    if elapsed < 1.5:
        sleep(1.5 - elapsed)

    return response
