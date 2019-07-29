from datetime import datetime
from hashlib import sha1
import re
import sys
from urlparse import urlsplit, parse_qs

from lxml import etree
import iso8601

from ocd_backend.items import BaseItem


class UtrechtItem(BaseItem):
    combined_index_fields = {
        'hidden': bool,
        'title': unicode,
        'description': unicode,
        'start_date': datetime,
        'end_date': datetime,
        'authors': list,
        'media_urls': list,
        'all_text': unicode,
        'id': unicode,
        'status': unicode,
        'sender': unicode,
        'categories': list
    }

    def _get_text_or_none(self, xpath_expression):
        node = self.original_item.find(xpath_expression)
        if node is not None and node.text is not None:
            return unicode(node.text)

    def _get_title(self):
        try:
            return unicode(
                self.original_item.xpath(
                    ".//meta[@property='og:title']/@content")[0])
        except LookupError:
            return unicode(
                u''.join(self.original_item.xpath(
                    ".//title/text()")))

    def _get_url(self):
        try:
            return unicode(self.original_item.xpath(
                ".//meta[@property='og:url']/@content")[0])
        except LookupError:
            rsbtn_url = self.original_item.xpath(
                ".//a[@class='rsbtn_play']/@href")[0]
            rsbtn_info = urlparse(rsbtn_url)
            rsbtn_query = parse_qs(rsbtn_info.query)
            return unicode(rsbtn_query['url'])

    def _get_basic_info(self):
        """
        Returns a tuple of id, status and title.
        """
        # Title
        wob_title = None
        wob_status = u''
        wob_id = None
        wob_title = self._get_title()
        #print >>sys.stderr, etree.tostring(self.original_item)
        print >>sys.stderr, "URL: %s" % (self._get_url(),)
        print >>sys.stderr, "Title: %s" % (wob_title,)

        if wob_title:
            wob_id, wob_status, actual_title = wob_title.split(
                u' ', 2)

            if not re.match('^\d{4}', wob_id):
                # Use slug as object id
                wob_id = unicode(self._get_url().split('/')[-2])
        if wob_status.lower() in ['wob-besluit', 'wob-besluiten', 'wob']:
            wob_status = u'Besluit'

        return (wob_id, wob_status, wob_title,)

    def _get_hashed_id(self, wob_id):
        # leftpad with zeroes if necessary
        if len(wob_id) < 3:
            try:
                wob_id = u'%03d' % (int(wob_id),)
            except ValueError:
                pass
        obj_id = u'%s:%s' % (self.source_definition['index_name'], wob_id,)
        hashed_obj_id = sha1(obj_id.decode('utf8')).hexdigest()
        print >>sys.stderr, "Checking Wob ID: %s, Class: %s, Hash id: %s" % (
            wob_id, self.__class__, hashed_obj_id,)
        return unicode(hashed_obj_id)

    def get_object_id(self):
        wob_id, wob_status, wob_title = self._get_basic_info()
        # Use slug as object id
        return self._get_hashed_id(wob_id)

    def get_original_object_id(self):
        wob_id, wob_status, wob_title = self._get_basic_info()
        print >>sys.stderr, "Wob ID: %s" % (wob_id,)
        # Use slug as object id
        return wob_id

    def get_original_object_urls(self):
        url = unicode(self._get_url())

        # Check if we are dealing with an archived page, if true then
        # prepend the archive URL to the original URL
        archive_url = unicode(
            self.original_item.xpath(".//link[@rel='stylesheet']/@href")[
                -1].split('http')[1])

        if 'archiefweb.eu' in archive_url:
            url = u'http' + archive_url + url

        if self.original_item.xpath(".//time/@datetime"):
            item_date = datetime.strptime(
                self.original_item.xpath(".//time/@datetime")[0],
                '%Y-%m-%dT%H:%M'
            )
        else:
            item_date = datetime.datetime.now()

        if 'archiefweb.eu' in url:
            alternate_url = url
        else:
            alternate_url = (
                u'https://archief12.archiefweb.eu/archives/archiefweb/'
                u'%s/%s') % (item_date.strftime('%Y%m%d%H%m%S'), url,)

        return {
            'html': url,
            'alternate': alternate_url
        }

    def get_rights(self):
        return u'Undefined'

    def get_collection(self):
        return u'Utrecht'

    def get_combined_index_data(self):
        combined_index_data = {
            'hidden': self.source_definition['hidden']
        }

        # Title
        wob_id, wob_status, wob_title = self._get_basic_info()
        combined_index_data['title'] = wob_title
        if re.match('^\d{4}', wob_id):
            combined_index_data['id'] = self._get_hashed_id(wob_id)
            combined_index_data['status'] = wob_status

        # Description
        # Case for new website design
        if self.original_item.xpath("(.//div[@class='limiter']/p)[1]//text()"):
            combined_index_data['description'] = unicode(
                ''.join(
                    self.original_item.xpath(
                        "(.//div[@class='limiter']/p)[1]//text()")))

        # Case for old website design
        elif self.original_item.xpath(
            "(.//div[@class='news-single-item']/p)[1]//text()"
        ):
            combined_index_data['description'] = unicode(
                ''.join(self.original_item.xpath(
                    "(.//div[@class='news-single-item']/p)[1]//text()")))

        # Date
        if self.original_item.xpath(".//time/@datetime"):
            combined_index_data['end_date'] = datetime.strptime(
                self.original_item.xpath(".//time/@datetime")[0],
                '%Y-%m-%dT%H:%M'
            )

        # media urls
        combined_index_data['media_urls'] = []
        for u in self.original_item.xpath(".//a[@class='download']"):
            actual_url = u''.join(u.xpath('./@href'))
            label = u''.join(u.xpath('.//text()'))
            if actual_url.startswith(u'/'):
                actual_url = u'https://www.utrecht.nl%s' % (actual_url,)
            if actual_url.lower().endswith('.pdf'):
                combined_index_data['media_urls'].append({
                    'original_url': actual_url,
                    'content_type': u'application/pdf',
                    'label': label
                })

        return combined_index_data

    def get_index_data(self):
        return {}

    def get_all_text(self):
        text_items = []

        return u' '.join(text_items)


class UtrechtCategoryItem(UtrechtItem):
    combined_index_fields = {
        'categories': list
    }

    def _get_title(self):
        return self.original_item['title']

    def _get_url(self):
        return self.original_item['url']

    def get_original_object_urls(self):
        if 'archiefweb.eu' in self.original_item['url']:
            alternate_url = self.original_item['url']
        else:
            alternate_url = (
                u'https://archief12.archiefweb.eu/archives/archiefweb/'
                u'%s/%s') % (
                    datetime.now().strftime('%Y%m%d%H%m%S'),
                    self.original_item['url'],)

        return {
            'html': self.original_item['url'],
            'alternate': alternate_url
        }

    def get_rights(self):
        return u'Undefined'

    def get_collection(self):
        return u'Utrecht'

    def get_combined_index_data(self):
        doc = {
            'categories': self.original_item['categories']
        }
        return doc


class UtrechtOverviewItem(UtrechtItem):
    def _get_title(self):
        return u'%s Openstaand %s' % (
            self.original_item['id'], self.original_item['title'],)

    def _get_url(self):
        return u''

    def get_original_object_urls(self):
        return {}

    def get_rights(self):
        return u'Undefined'

    def get_collection(self):
        return u'Utrecht'

    def get_combined_index_data(self):
        combined_index_data = {
            'hidden': self.source_definition['hidden'],
        }

        wob_id, wob_status, wob_title = self._get_basic_info()
        combined_index_data['title'] = wob_title
        combined_index_data['id'] = self._get_hashed_id(wob_id)

        if self.original_item['date'] is not None:
            combined_index_data['start_date'] = iso8601.parse_date(
                self.original_item['date'])
        combined_index_data['status'] = u'Openstaand'

        return combined_index_data
