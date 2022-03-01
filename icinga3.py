#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Linuxfabrik GmbH, Zurich, Switzerland
# Contact: info (at) linuxfabrik (dot) ch
#          https://www.linuxfabrik.ch/
# License: The Unlicense, see LICENSE file.

# https://github.com/Linuxfabrik/monitoring-plugins/blob/main/CONTRIBUTING.rst

"""This module tries to make accessing the Icinga2 API easier.
"""

__author__ = 'Linuxfabrik GmbH, Zurich/Switzerland'
__version__ = '2022021601'

import base64
import time

from . import txt3
from . import url3

# Take care of Icinga and throttle the amount of requests, don't overload it
# with too fast subsequent api-calls.
DEFAULT_SLEEP = 1.0


def api_post(url, username, password, data={}, method_override='',
             insecure=True, no_proxy=False, timeout=3):
    """POST a low level (handmade) request to the Icinga API.

    Example:
    >>> url = 'https://icinga-server:5665/v1/objects/services'
    >>> data = {
    >>>    'filter': 'match("special-service", service.name)',
    >>>    'attrs': [ 'name', 'state', 'acknowledgement' ],
    >>> }
    >>> result = lib.base.coe(lib.icinga.api_post(url, args3.USERNAME,
    >>>                       args3.PASSWORD, data=data,
    >>>                       method_override='GET', timeout=3))
    """

    url = url.replace('//v1', '/v1').replace('//v2', '/v2')
    header = {}
    header['Accept'] = 'application/json'
    auth = '{}:{}'.format(username, password)
    encoded_auth = txt3.to_text(base64.b64encode(txt3.to_bytes(auth)))
    header['Authorization'] = 'Basic {}'.format(encoded_auth)
    if method_override:
        header['X-HTTP-Method-Override'] = method_override
    result = url3.fetch_json(
        url,
        data=data,
        encoding='serialized-json',
        header=header,
        insecure=insecure,
        no_proxy=no_proxy,
        timeout=timeout,
    )
    time.sleep(DEFAULT_SLEEP)
    return result


def get_service(url, username, password, servicename, attrs='state'):
    """POST a high level request to the Icinga `objects/service` API
    (with less possibilities). The service name should be unique and has
    to be taken from the `__name` attribute.

    Example: Does a check show a warning and/or was acknowledged?

    >>> url = 'https://icinga-server:5665'
    >>> result = lib.base.coe(
    >>>     lib.icinga.get_service(
    >>>         url,
    >>>         args3.USERNAME,
    >>>         args3.PASSWORD,
    >>>         servicename='hostname!special-service',
    >>>         attrs='state,acknowledgement',
    >>>         ))
    >>> print(result['result'][0]['attrs'])
    """

    url = url + '/v1/objects/services'
    data = {
        'filter': 'match("{}", service.__name)'.format(servicename),
        'attrs': ['name'] + attrs.split(','),
    }
    return api_post(
        url=url,
        username=username,
        password=password,
        data=data,
        method_override='GET',
        insecure=True,
    )


def set_ack(url, username, password, objectname, _type='service',
            author='Linuxfabrik lib.icinga'):
    """Allows you to acknowledge the current problem for hosts or
    services. By acknowledging the current problem, future notifications
    (for the same state if sticky is set to false) are disabled.  The
    host or service name should be unique and has to be taken from the
    `__name` attribute.

    Acknowledging an already acknowledged problem is ok until 2.11, while
    acknowleding a host or service in OK state leads to a *500 internal
    server error".
    """

    url = url + '/v1/actions/acknowledge-problem'
    data = {
        'type': _type.capitalize(),
        'filter': 'match("{}", {}.__name)'.format(objectname, _type.lower()),
        'author': author,
        'comment': 'automatically acknowledged',
        'notify': False,
    }
    return api_post(
        url=url,
        username=username,
        password=password,
        data=data,
        insecure=True,
    )


def set_downtime(url, username, password, objectname, _type='service',
                 starttime=int(time.time()),
                 endtime=int(time.time())+60*60,
                 author='Linuxfabrik lib.icinga'):
    """POST a high level request to the Icinga `actions/schedule-downtime
    API (with less possibilities). The host or service name should be
    unique and has to be taken from the `__name` attribute.

    You will get a downtime name, which you have to use if you want to
    use `remove_ack()` later on.

    >>> url = 'https://icinga-server:5665'
    >>> result = lib.base.coe(lib.icinga.set_downtime(
    >>>              url,
    >>>              args3.ICINGA_USERNAME,
    >>>              args3.ICINGA_PASSWORD,
    >>>              objectname='hostname!special-service',
    >>>              author='feed plugin',
    >>>              ))
    'hostname!special-service!3ad20784-52f9-4acc-b2df-90788667d587'
    """

    url = url + '/v1/actions/schedule-downtime'
    data = {
        'type': _type.capitalize(),
        'filter': 'match("{}", {}.__name)'.format(objectname, _type.lower()),
        'author': author,
        'comment': 'automatic downtime',
        'start_time': starttime,
        'end_time': endtime,
    }
    success, result = api_post(
        url=url,
        username=username,
        password=password,
        data=data,
        insecure=True,
    )
    if success and result['results'][0]['code'] == 200:
        return (True, result['results'][0]['name'])
    return (False, result)


def remove_ack(url, username, password, objectname, _type='service'):
    """Removes the acknowledgements for services or hosts. Once the
    acknowledgement has been removed the next notification will be sent
    again. Always returns ok.

    >>> url = 'https://icinga-server:5665'
    >>> icinga3.remove_ack(
    >>>     url,
    >>>     args3.ICINGA_USERNAME,
    >>>     args3.ICINGA_PASSWORD,
    >>>     objectname='hostname!special-service',
    >>>     )
    """

    url = url + '/v1/actions/remove-acknowledgement'
    data = {
        'type': _type.capitalize(),
        'filter': 'match("{}", {}.__name)'.format(objectname, _type.lower()),
    }
    return api_post(url=url,
        username=username,
        password=password,
        data=data,
        insecure=True,
    )


def remove_downtime(url, username, password, downtime):
    """Remove the downtime using its name you got from `set_downtime()`.
    Always returns ok.
    """

    url = url + '/v1/actions/remove-downtime'
    data = {
        'downtime': downtime,
    }
    return api_post(url=url,
        username=username,
        password=password,
        data=data,
        insecure=True,
    )
