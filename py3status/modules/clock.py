# -*- coding: utf-8 -*-
"""
Display time and date information.

This module allows one or more datetimes to be displayed.
All datetimes share the same format_time but can set their own timezones.
Timezones are defined in the `format` using the TZ name in squiggly brackets eg
`{GMT}`, `{Portugal}`, `{Europe/Paris}`, `{America/Argentina/Buenos_Aires}`.

ISO-3166 two letter country codes eg `{de}` can also be used but if more than
one timezone exists for the country eg `{us}` the first one will be selected.

`{Local}` can be used for the local settings of your computer.

Note: Timezones are case sensitive

A full list of timezones can be found at
https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

Configuration parameters:
    blocks: a string, where each character represents time period
        from the start of a time period.
        (default '🕛🕧🕐🕜🕑🕝🕒🕞🕓🕟🕔🕠🕕🕡🕖🕢🕗🕣🕘🕤🕙🕥🕚🕦')
    block_hours: length of time period for all blocks in hours (default 12)
    button_change_format: button that switches format used setting to 0
        disables (default 1)
    button_change_time_format: button that switches format_time used. setting
        to 0 disables (default 2)
    button_reset: button that switches display to the first timezone. setting
        to 0 disables (default 3)
    cycle: If more than one display then how many seconds between changing the
        display (default 10)
    format: defines the timezones displayed these can be separated by `;` for
        multiple displays that are switched between (default '{Local}')
    format_time: format to use for the time, strftime directives such as `%H`
        can be used
        (default ['[{name_} ]%c', '[{name_} ]%x %X',
        '[{name_} ]%a %H:%M', '[{name_} ]{icon}'])

Format of status string placeholders:
    {icon} a character representing the time from `blocks`
    {name} friendly timezone name eg `Buenos Aires`
    {timezone} full timezone name eg `America/Argentina/Buenos_Aires`

Requires:
    pytz: python library
    tzlocal: python library

i3status.conf example:

```
# cycling through London, Warsaw, Tokyo
clock {
    format = "{Europe/London};{Europe/Warsaw};{Asia/Tokyo}"
    format_time = "{name} %H:%M"
}


# Show the time and date in New York
clock {
   format = "Big Apple {America/New_York}"
   format_time = "%Y-%m-%d %H:%M:%S"
}


# wall clocks
clock {
    format = "{Asia/Calcutta} {Africa/Nairobi} {Asia/Bangkok}"
    format_time = "{name} {icon}"
}
```

@author tobes
@license BSD

"""

import re
import math
from datetime import datetime
from time import time

import pytz
import tzlocal

CLOCK_BLOCKS = u'🕛🕧🕐🕜🕑🕝🕒🕞🕓🕟🕔🕠🕕🕡🕖🕢🕗🕣🕘🕤🕙🕥🕚🕦'


class Py3status:
    """
    """
    # available configuration parameters
    blocks = CLOCK_BLOCKS
    block_hours = 12
    button_change_format = 1
    button_change_time_format = 2
    button_reset = 3
    cycle = 0
    format = "{Local}"
    format_time = [
        '[{name_} ]%c',
        '[{name_} ]%x %X',
        '[{name_} ]%a %H:%M',
        '[{name_} ]{icon}',
    ]

    def post_config_hook(self):
        # Multiple clocks are possible that can be cycled through
        if not isinstance(self.format, list):
            self.format = [self.format]
        # if only one item we don't need to cycle
        if len(self.format) == 1:
            self.cycle = 0
        # find any declared timezones eg {Europe/London}
        self._items = {}
        matches = re.findall('\{([^}]*)\}', ''.join(self.format))
        for match in matches:
            self._items[match] = self._get_timezone(match)

        self.multiple_tz = len(self._items) > 1

        if not isinstance(self.format_time, list):
            self.format_time = [self.format_time]

        # workout how often in seconds we will need to do an update to keep the
        # display fresh
        self.time_deltas = []
        for format in self.format_time:
            format_time = re.sub('\{([^}]*)\}', '', format)
            format_time = format_time.replace('%%', '')
            if '%f' in format_time:
                # microseconds
                time_delta = 0
            elif '%S' in format_time:
                # seconds
                time_delta = 1
            elif '%c' in format_time:
                # Locale’s appropriate date and time representation
                time_delta = 1
            elif '%X' in format_time:
                # Locale’s appropriate time representation
                time_delta = 1
            else:
                time_delta = 60
            self.time_deltas.append(time_delta)

        self.active_time_format = 0

        self._cycle_time = time() + self.cycle
        self.active = 0

    def _get_timezone(self, tz):
        '''
        Find and return the time zone if possible
        '''
        # special Local timezone
        if tz == 'Local':
            try:
                return tzlocal.get_localzone()
            except pytz.UnknownTimeZoneError:
                return '?'

        # we can use a country code to get tz
        # FIXME this is broken for multi-timezone countries eg US
        # for now we just grab the first one
        if len(tz) == 2:
            try:
                zones = pytz.country_timezones(tz)
            except KeyError:
                return '?'
            tz = zones[0]

        # get the timezone
        try:
            zone = pytz.timezone(tz)
        except pytz.UnknownTimeZoneError:
            return '?'
        return zone

    def _change_active(self, diff):
        self.active = (self.active + diff) % len(self.format)

    def on_click(self, i3s_output_list, i3s_config, event):
        """
        Switch the displayed module or pass the event on to the active module
        """
        # reset cycle time
        if event['button'] == self.button_reset:
            self.active = 0
            # reset the cycle time
            self._cycle_time = time() + self.cycle
        elif event['button'] == self.button_change_time_format:
            self.active_time_format += 1
            if self.active_time_format >= len(self.format_time):
                self.active_time_format = 0
        elif event['button'] == self.button_change_format:
            self._change_active(1)

    def clock(self, i3s_output_list, i3s_config):

        # cycling
        if self.cycle and time() >= self._cycle_time:
            self._change_active(1)
            self._cycle_time = time() + self.cycle

        # update our times
        times = {}
        for name, zone in self._items.items():
            if zone == '?':
                times[name] = '?'
            else:
                t = datetime.now(zone)
                format_time = self.format_time[self.active_time_format]
                icon = None
                if '{icon}' in format_time:
                    # calculate the decimal hour
                    h = t.hour + t.minute / 60.
                    # make 12 hourly etc
                    h = h % self.block_hours
                    idx = int(math.floor(h / self.block_hours * (len(
                        self.blocks))))
                    icon = self.blocks[idx]

                timezone = zone.zone
                tzname = timezone.split('/')[-1].replace('_', ' ')
                name_ = tzname if self.multiple_tz else None

                format_time = self.py3.safe_format(format_time,
                                                   dict(
                                                       icon=icon,
                                                       name=tzname,
                                                       name_=name_,
                                                       timezone=timezone
                                                    ))
                if self.py3.is_python_2():
                    format_time = t.strftime(format_time.encode('utf-8'))
                else:
                    format_time = t.strftime(format_time)
                times[name] = format_time

        # work out when we need to update
        now = time()
        if self.time_deltas[self.active_time_format]:
            timeout = (now + self.time_deltas[self.active_time_format]
                       - now % self.time_deltas[self.active_time_format])
        else:
            timeout = 0

        # if cycling we need to make sure we update when they are needed
        if self.cycle:
            cycle_timeout = self._cycle_time
            timeout = min(timeout, cycle_timeout)

        return {
            'full_text': self.py3.safe_format(self.format[self.active], times),
            'cached_until': timeout
        }


if __name__ == "__main__":
    """
    Test this module by calling it directly.
    """
    from time import sleep
    x = Py3status()
    config = {'color_bad': '#FF0000', 'color_good': '#00FF00', }

    while True:
        print(x.clock([], config))
        sleep(1)
