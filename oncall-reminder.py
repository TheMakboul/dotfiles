#!/usr/bin/python

import re
import json
import pycurl
import urllib
import xml.etree.ElementTree as et
from datetime import date
from string import Template
from StringIO import StringIO

def fetch_data():
    '''Make request to Confluence for the on-call page content to return as a str.'''
    io = StringIO()
    c = pycurl.Curl()
    c.setopt(c.USERPWD, 'webproducts-dashboar:2%roadsNYT')
    c.setopt(c.URL, 'https://confluence.nyt.net/rest/api/content/38153944?expand=body.view')
    c.setopt(c.WRITEFUNCTION, io.write)
    c.perform()
    c.close()

    return io.getvalue()

def parse_body(api_response):
    '''Convert response str to JSON and return the body content as a str.'''
    try:
        json_data = json.loads(api_response)
    except:
        return None

    try:
        body_content = json_data['body']['view']['value']
    except:
        return None

    return body_content

def parse_table(body):
    '''Get rid of the markup before the table, as it causes XPathing to fail.'''
    pattern = re.compile('.*(<table .*<\/table>)')
    match = pattern.match(body)
    if match is None: return None

    return match.group(1)

def get_week_number():
    '''Get the numerical week value as an int'''
    d = date.today()
    ic = d.isocalendar()
    week_num = ic[1]
    if week_num < 10:
        week_num = '0' + str(week_num)

    return week_num 

def get_current_week_row(data_rows):
    '''Find table row containing current week's info.'''
    current_week = str(get_week_number())
    week_pattern = re.compile('(\d+)')
    for row in data_rows:
        cell = row.find('.//td/span')
        if cell is None: continue
        match = week_pattern.match(cell.tail)
        if match is None: continue
        if match.group(1) == current_week:
            return row

    return None

def parse_names(table_row):
    '''Get the names of those on call from the row markup object.'''
    try:
        root = et.fromstring(table_row.encode('ascii', 'ignore'))
    except Exception, e:
        return None

    # Find row corresponding to the current week, which would be a lot simpler
    # if the available version of Python were newer (very limited XPath support
    # in Python 2.6 apparently)
    rows = root.findall('.//tr')
    if len(rows) == 0: return None

    current_row = get_current_week_row(rows)
    if current_row is None: return None

    paragraphs = current_row.findall('.//td/p')
    if len(paragraphs) == 0: return None

    names = []

    for p in paragraphs:
        # Some values are placed directly in the P tag, while others are nested within a SPAN,
        # while others are nested within a SPAN within a SPAN
        if p.text is not None:
            names.append(p.text)
        else:
            # Any more silliness in the structure of the data than this will call for using a recursive function
            span = p.find('./span')
            if span is not None and span.text is not None:
                names.append(span.text)
            else:
                subspan = span.find('./span')
                if subspan is not None and subspan.text is not None:
                    names.append(subspan.text)

    return names

def post_message(names):
    '''Post message to Slack about the on call rotation.'''
    proxy = 'http://proxy-squid.dev.ewr1.nytimes.com'
    proxy_port = 80
    url = 'https://hooks.slack.com/services/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'
    channel = '#nyt5-jenkins-alerts'
    username = 'On Call Reminder'
    icon = ':monkeyspa:'
    message = '<!channel> New NYT5 daytime on call rotation starts now. '

    if names is not None and len(names) > 0:
        formatted_names = ['\n*' + name + '*' for name in names]
        message += 'Up this week:\n' + ''.join(formatted_names)
    else:
        message += 'Unable to retrieve names of those up this week. See the <https://confluence.nyt.net/display/GNP/NYT5+daytime+On+Call+for+Jenkins|schedule>.'

    post_body = Template('payload={"channel": "$channel", "username": "$username", "text": "$message", "icon_emoji": "$icon"}')
    post_body = post_body.substitute(channel=channel, username=username, message=message, icon=icon)

    c = pycurl.Curl()
    c.setopt(c.PROXY, proxy)
    c.setopt(c.PROXYPORT, proxy_port)
    c.setopt(c.CUSTOMREQUEST, 'POST')
    c.setopt(c.URL, url)
    c.setopt(c.POSTFIELDS, post_body)
    c.perform()
    c.close()

api_response = fetch_data()
body = parse_body(api_response)
parsed_table = parse_table(body)
names = parse_names(parsed_table)
post_message(names)

