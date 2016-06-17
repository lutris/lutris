import re
import sys
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




class SteamBanScraper(object):
    """Scraper to download banners from."""

    def __init__(self, rename_best_ranked=True, safe_only=False, headers={'User-Agent':'Mozilla/5.0'}):
        
        self.renameBestRanked = rename_best_ranked
        self.safeOnly = safe_only
        self.headers = headers	

        self.tasks = multiprocessing.JoinableQueue()
        self.results = multiprocessing.Queue()
        self.numConsumers = multiprocessing.cpu_count() * 8

        self.bannerPages = []
        self.consumers = []

    def search(self, query, from_scratch=False):
        """Search for _query_ banners and update self.bannerPages with those links"""

        self.url = 'http://steambanners.booru.org/index.php?page=post&s=list&tags={}'\
                   .format(query.replace(' ', '_'))
        
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
            self.numConsumers = min(len(self.bannerPages), self.numConsumers)

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

        # wait for tasks to finish
        for consumer in self.consumers:
            consumer.join()
    
        # get results
        self.bannerMeta = []
        while not self.results.empty():
            self.bannerMeta.append(self.results.get())

        # drop poison pill to terminate remaining processes
        for consumer in self.consumers:
            self.tasks.put(None)

        # rename the banner with the highest score to 'default.*g'
        if self.renameBestRanked and self.bannerMeta:
            best_ranked_id = max(self.bannerMeta, key=lambda x:x['score'])['id']
            best_ranked_name = glob.glob( os.path.join(save_dir, best_ranked_id + "*"))[0]
            os.rename(best_ranked_name, best_ranked_name.replace(best_ranked_id, 'default'))


class BanConsumer(multiprocessing.Process): 
    
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
            for i in range(self.connectionAttempts):
            #while True:
                answer, task = next_task(self.numConsumers)
                if answer is not None: 
                    break
            # Adding another task before task_done makes sure
            # the task_queue never gets empty too early
            self.task_queue.put(task)
            self.task_queue.task_done()
            self.result_queue.put(answer)    
        return
	

class DlTask(object):

    def __init__(self, banner_page, save_dir, safe_only=False, headers={'User-meta':'Mozilla/5.0'}):
        self.headers = headers
        self.bannerPageUrl = 'http://steambanners.booru.org/' + banner_page
        self.saveDir = save_dir
        self.safeOnly = safe_only

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

        return {'score':  int(banner_page.find('a', {'id':'psc'}).text),
                'url':    img_url,
                'rating': img_rating,
                'id':     img_id}, None        



class SearchTask(object):
    """"""

    def __init__(self, url, page_index, headers={'User-meta':'Mozilla/5.0'}):
        self.url = url
        self.pageIndex = page_index
        self.headers = headers

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



if __name__=='__main__':
    scraper = SteamBanScraper()
    scraper.search(" ".join(sys.argv[1:]))
    scraper.download(os.path.expanduser("~p"))

