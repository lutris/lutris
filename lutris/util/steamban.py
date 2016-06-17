#/usr/bin/env python2

"""
An asynchronous steambanners.booru.org scraper
"""

import re
import os
import glob
import multiprocessing

try: # Python3
    import urllib.request as rqst
    from urllib import HTTPError
except ImportError: #Python2
    import urllib2 as rqst
    from urllib2 import HTTPError

from bs4 import BeautifulSoup
from collections import OrderedDict


STEAMBANURL = 'http://steambanners.booru.org/'

REGEX_ROMAN = re.compile(r"^([M]{0,4}[CM|CD|DC]?[C]{0,3}[XC|XL|L]?[X]{0,3}[IX|IV|VI|I]{0,3})[\-0-9]*$")
REGEX_NUMBER = re.compile(r"^([0-9]*)[\-0-9]*$")

ROMAN = OrderedDict([
                        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'),
                        (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'),
                        (4, 'IV'), (1, 'I')
                    ])

NUMBER = { value:key for (key, value) in ROMAN.iteritems() }


class SteamBanScraper(object):
    """Scraper to download banners from steambanners.booru.org"""

    def __init__(self, rename_best_ranked=True, safe_only=False, headers={'User-Agent':'Mozilla/5.0'}):
        
        #super(SteamBanScraper, self).__init__()

        self.renameBestRanked = rename_best_ranked
        self.safeOnly = safe_only
        self.headers = headers	

        self.tasks = multiprocessing.JoinableQueue()

        self.results = multiprocessing.Queue()
        self.numConsumers = multiprocessing.cpu_count() * 8

        self.bannerPages = []
        self.consumers = []
        self.bannerMeta = []

    def search(self, query, match_tag_only=True, from_scratch=False):
        """Search for _query_ banners and update self.bannerPages with those links

        Several searches can be conducted one after another and at the end the
        bannerPages attribute will contain the links to the banners of the results
        of all those searches.

        For instance, one could use
        scraper.search('')
        """

        self.bannerPages = [] if from_scratch else self.bannerPages

        # create proper url
        if match_tag_only:
            self.url = STEAMBANURL + 'index.php?page=post&s=list&tags={}'\
                       .format(query.replace(' ', '_')) #restrictive
        else:
            self.url = STEAMBANURL + 'index.php?page=post&s=list&tags={}'\
                       .format(query.replace(' ', '+')) #broad
        
        # create search tasks for the first pages (1 per consumer)
        for i in range(self.numConsumers):
            self.tasks.put( SearchTask(self.url, i, self.headers) )
        
        # create and starts consumers
        for i in range(self.numConsumers):
            consumer = BanConsumer(self.tasks, self.results, self.numConsumers)
            consumer.start()
            self.consumers.append(consumer)
        
        # Wait for every task to be finished
        # (i.e. each consumer ran into an empty page)
        self.tasks.join()

        # Get results and add those to bannerPages
        while not self.results.empty():
            self.bannerPages.extend(self.results.get() or [])

        self.bannerPages = list(set(self.bannerPages))

        return len(self.bannerPages)
        
    def searchExtended(self, query, match_tag_only=True, from_scratch=False, separator='-', metaseparator=': '):
        """search for query with different versions of query banners

        In particular this is useful for game titles containing roman numerals
        or numbers, as this will look for both and combine results.
        """


        # do some early formatting (ADD MORE IF NEEDED)
        formatted_query = query.lower().replace('&','and')
        #if formatted_query.startswith('the'):
        #    formatted_query = formatted_query.replace('the'+separator, '')

        if metaseparator in formatted_query:
            formatted_query = formatted_query.split(metaseparator)[1]      

        # start from current banner pages or from scratch
        self.bannerPages = [] if from_scratch else self.bannerPages

        # Do normal & broad search
        self.search(formatted_query.replace(separator, '_') )
        if not match_tag_only:
            self.search( formatted_query.replace(separator, '+') )

        # search for roman numerals
        for word in query.split(separator):
            m = REGEX_ROMAN.match(word)
            if m is not None and m.group(1):

                formatted_query = roman_handle(formatted_query, m.group(1) )
                
                #search for query with roman replaced by numbers
                self.search(formatted_query.replace(separator, '_'))                
                if not match_tag_only:
                    self.search( formatted_query.replace(separator, '+') )
                
                # stop here if roman were found : so in case of mixed
                # romans + numbers, only the romans will be converted
                # (e.g final fantasy xiii-2 --> final-fantasy 13-2 )
                return len(self.bannerPages)

        # search for numbers
        for word in query.split(separator):
            m = REGEX_NUMBER.match(word)
            if m is not None and m.group(1):
                formatted_query = number_handle(formatted_query, m.group(1) )
                
                self.search(formatted_query.replace(separator, '_'))                
                if not match_tag_only:
                    self.search( formatted_query.replace(separator, '+') )

                return len(self.bannerPages)

        return len(self.bannerPages)

    def download(self, save_dir, n=0):
        """Download banners in save directory"""

        # Check if dir exist or make a new one
        if not os.path.exists(os.path.expanduser(save_dir)):
            os.mkdir(os.path.expanduser(save_dir))

        # Adjust the pages to download and the number of consumers to use
        if n == 0: 
            banner_pages_to_dl = self.bannerPages
        else:
            banner_pages_to_dl = self.bannerPages[:n]
            self.numConsumers = min(len(banner_pages_to_dl), self.numConsumers)

        # create download tasks for every banner_pages
        for page_url in banner_pages_to_dl:
            self.tasks.put(
                DlTask(page_url, save_dir, self.safeOnly, self.headers)
                )

        # create and starts consumers
        for i in range(self.numConsumers):
            consumer = BanConsumer(self.tasks, self.results, self.numConsumers)
            consumer.start()
            self.consumers.append(consumer)
    
        # wait for tasks to be finished
        self.tasks.join()

        # get results
        while not self.results.empty():
            self.bannerMeta.extend(self.results.get() or [])

        #drop poison pill to terminate remaining processes
        for consumer in self.consumers:
            self.tasks.put(None)

        # rename the banner with the highest score to 'default.*g'
        if self.renameBestRanked and self.bannerMeta:
            best_ranked_id = max(self.bannerMeta, key=lambda x:x['score'])['id']
            best_ranked_name = glob.glob( os.path.join(save_dir, best_ranked_id + "*"))[0]
            os.rename(best_ranked_name, best_ranked_name.replace(best_ranked_id, 'default'))


class BanConsumer(multiprocessing.Process): 
    """Commmon consumer for download & scraping"""

    def __init__(self, task_queue, result_queue, num_consumers, connection_attempts=20):
        super(BanConsumer, self).__init__()
        self.task_queue = task_queue
        self.connectionAttempts = connection_attempts
        self.result_queue = result_queue
        self.numConsumers = num_consumers


    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            # Poison pill
            if next_task is None:
                self.task_queue.task_done()
                break
            
            # This loops takes care of connection errors
            # and will keep going until connection does not 
            # fail or connectionAttempts threshold reached
            #for i in range(self.connectionAttempts):
            elif next_task:
                while True:
                    answer, task = next_task(self.numConsumers)
                    if answer is not None: 
                        break
            
            # Adding another task before task_done makes sure
            # the task_queue never gets empty too early
                self.task_queue.put(task)
                self.task_queue.task_done()
                self.result_queue.put(answer)
            
            else:
                self.task_queue.task_done()    
        
        return

	
class DlTask(object):

    def __init__(self, banner_suffix, save_dir, safe_only=False, headers={'User-meta':'Mozilla/5.0'}):
        self.headers = headers
        self.bannerPageUrl = STEAMBANURL + banner_suffix
        self.saveDir = save_dir
        self.safeOnly = safe_only

    def __bool__(self):
        return True

    def __call__(self, *args, **kwargs):
        try: # Connect to the banner page
            req  = rqst.Request(self.bannerPageUrl, headers=self.headers)
            con  = rqst.urlopen(req)
            banner_page = BeautifulSoup(con.read(), 'html.parser')
        except HTTPError:
            return None, None
        
        # Get banner image link & information
        img_url = banner_page.find('img', {'id':'image'})['src']
        img_id = re.search(r"id=([0-9]*)", self.bannerPageUrl).group(1)
        img_rating = re.search(r"Rating: ([^\n]*)",
                                 banner_page.find('div', {'id':'tag_list'}).text
                                ).group(1)

        if img_rating == "Safe" or not self.safeOnly:

            try: # Connect to the the banner img 
                img_req = rqst.Request(img_url, headers=self.headers)
                img_con  = rqst.urlopen(img_req)
                mime = img_con.info()['Content-type']

                # Check the file mimetype to set the extension
                if mime.endswith('jpeg'):
                    filename = img_id+os.path.extsep+'jpg'
                else:
                    filename = img_id+os.path.extsep+mime[-3:]

                with open(os.path.join(self.saveDir, filename), 'wb') as img_file:
                    img_file.write(img_con.read())
            except HTTPError:
                return None, None

        return [{'score':  int(banner_page.find('a', {'id':'psc'}).text),
                'url':    img_url,
                'rating': img_rating,
                'id':     img_id}], NoTask()        


class SearchTask(object):
    """"""

    def __init__(self, url, page_index, headers={'User-meta':'Mozilla/5.0'}):
        self.url = url
        self.pageIndex = page_index
        self.headers = headers

    def __bool__(self):
        return True

    def __call__(self, num_consumers, *args, **kwargs):

        try: # Connect to the search page
            req  = rqst.Request(self.url + '&pid={}'.format(self.pageIndex*20), headers=self.headers)
            con  = rqst.urlopen(req)
            page = BeautifulSoup(con.read(), 'html.parser')
        except HTTPError:
            return None, None

        # Look for every banner page link
        thumbs = [ thumb.find('a')['href'] 
                   for thumb in page.findAll('span', {'class':'thumb'}) ]

        # if thumbs are found we can assume there are more images somewhere,
        # so that means every Worker must have encountered an empty page 
        # once to stop going further in indexes.
        if thumbs: 
            return thumbs, SearchTask(self.url, self.pageIndex + num_consumers, self.headers)
        else:
            return thumbs, None


class NoTask():

    def __init__(self, *args, **kwargs):
        pass

    def __bool__(self):
        return False

    def __nonzero__(self):
        return False



def num2roman(num):
    """Create a generator which converts number to roman"""
    for r in ROMAN.keys():
        x, y = divmod(num, r)
        yield ROMAN[r] * x
        num -= (r * x)
        if num > 0:
            num2roman(num)
        else:
            break

def roman2num(roman):
    """ Create a generator which converts roman to number"""
    index, l = 0, len(roman)
    while index < l:
        if roman[index:index+2] in NUMBER.keys():
            yield NUMBER[ roman[index:index+2].upper() ]
            index += 2
        else:
            yield NUMBER[ roman[index].upper() ]
            index += 1

def roman_handle(query, roman):
    number = sum([n for n in roman2num(roman) ])
    return query.replace(roman, number)

def number_handle(query, number):
    """Taken from here: http://stackoverflow.com/a/28777781/6234244"""
    print(query, number)
    roman = "".join([a for a in num2roman(int(number))])
    return query.replace(number, roman)







if __name__=='__main__':

    import argparse
    parser = argparse.ArgumentParser(description="Download banners from Steam Banner",
                                     usage='%(prog)s DIR QUERY... [-n N] [-r] [-s] [-l]')
    parser.add_argument('save_dir', metavar='DIR', type=str, 
                        help='the directory to save banners in')
    parser.add_argument('query', metavar='QUERY', type=str, nargs='+',
                        help='the game to look for (spaces accepted)')
    parser.add_argument('-n', type=int, required=False, default=[0], nargs=1,
                        help='number of banners to download')
    parser.add_argument('-s', required=False, action='store_true',
                        help='restrict to safe content')
    parser.add_argument('-r', required=False, action='store_true',
                        help='rename best ranked banner to default.jpg or default.png')
    parser.add_argument('-l', required=False, action='store_false',
                        help='perform a large search (words as separated tags)')

    args = parser.parse_args()

    scraper = SteamBanScraper(args.r, args.s)
    scraper.searchExtended(" ".join(args.query), match_tag_only=args.l, separator=' ')
    scraper.download(args.save_dir, args.n[0])

