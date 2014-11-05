"""
Model classes for the Humble Bundle API

This module only is guaranteed to only contain model class definitions
"""

__author__ = "Joel Pedraza"
__copyright__ = "Copyright 2014, Joel Pedraza"
__license__ = "MIT"


class BaseModel(object):
    def __init__(self, client, data):
        self._client = client

    def __str__(self):
        return str({key: self.__dict__[key]
                    for key in self.__dict__ if key != '_client'})

    def __repr__(self):
        return repr(self.__dict__)

    def __iter__(self):
        return self.__dict__.__iter__()


class Order(BaseModel):
    def __init__(self, client, data):
        super(Order, self).__init__(client, data)
        self.product = Product(client, data['product'])
        subscriptions = data.get('subscriptions', [])
        self.subscriptions = [
            Subscription(client, sub) for sub in subscriptions
        ] if len(subscriptions) > 0 else None
        self.thankname = data.get('thankname', None)
        self.claimed = data.get('claimed', None)
        self.gamekey = data.get('gamekey', None)
        self.country = data.get('country', None)
        self.giftee = data.get('giftee', None)
        self.leaderboard = data.get('leaderboard', None)
        self.owner_username = data.get('owner_username', None)
        self.platform = data.get('platform', None)
        self.subproducts = ([Subproduct(client, prod)
                             for prod in data.get('subproducts', [])]) or None

    def __repr__(self):
        return "Order: <%s>" % self.product.machine_name


class Product(BaseModel):
    def __init__(self, client, data):
        super(Product, self).__init__(client, data)
        self.category = data.get(1, None)
        self.human_name = data['human_name']
        self.machine_name = data['machine_name']
        self.supports_canonical = data['supports_canonical']

    def __repr__(self):
        return "Product: <%s>" % self.machine_name


class StoreProduct(BaseModel):
    def __init__(self, client, data):
        super(StoreProduct, self).__init__(client, data)
        self.category = data.get(1, None)
        self.human_name = data['human_name']
        self.machine_name = data['machine_name']
        self.current_price = Price(client, data['current_price'])
        self.full_price = Price(client, data['full_price'])
        self.icon = data['storefront_icon']  # URL as string
        self.platforms = data['platforms']  # linux, windows, mac
        # download, steam, origin
        self.delivery_methods = data['delivery_methods']
        self.description = data['description']  # HTML
        self.content_types = data['content_types']
        self.youtube_id = data['youtube_link']  # ID of youtube video
        self.esrb_rating = data['esrb_rating']
        self.pegi_rating = data['pegi_rating']
        self.developers = data['developers']  # dictionary
        self.publishers = data['publishers']
        self.allowed_territories = data['allowed_territories']
        self.minimum_age = data['minimum_age']
        self.system_requirements = data['system_requirements']  # HTML

    def __repr__(self):
        return "StoreProduct: <%s>" % self.machine_name


class Subscription(BaseModel):
    def __init__(self, client, data):
        super(Subscription, self).__init__(client, data)
        self.human_name = data['human_name']
        self.list_name = data['list_name']
        self.subscribed = data['subscribed']

    def __repr__(self):
        return "Subscription: <%s : %s>" % (self.list_name, self.subscribed)


class Subproduct(BaseModel):
    def __init__(self, client, data):
        super(Subproduct, self).__init__(client, data)
        self.machine_name = data['machine_name']
        self.payee = Payee(client, data['payee'])
        self.url = data['url']
        self.downloads = [Download(client, download)
                          for download in data['downloads']]
        self.human_name = data['human_name']
        self.custom_download_page_box_html = data[
            'custom_download_page_box_html'
        ]
        self.icon = data['icon']

    def __repr__(self):
        return "Subproduct: <%s>" % self.machine_name


class Payee(BaseModel):
    def __init__(self, client, data):
        super(Payee, self).__init__(client, data)
        self.human_name = data['human_name']
        self.machine_name = data['machine_name']

    def __repr__(self):
        return "Payee: <%s>" % self.machine_name


class Download(BaseModel):
    def __init__(self, client, data):
        super(Download, self).__init__(client, data)
        self.machine_name = data['machine_name']
        self.platform = data['platform']
        self.download_struct = [DownloadStruct(client, struct)
                                for struct in data['download_struct']]
        self.options_dict = data['options_dict']
        self.download_identifier = data['download_identifier']
        self.download_version_number = data['download_version_number']

    def sign_download_url(self, *args, **kwargs):
        return self._client.sign_download_url(
            self.machine_name, *args, **kwargs
        )

    def __repr__(self):
        return "Download: <%s>" % self.machine_name


class DownloadStruct(BaseModel):
    def __init__(self, client, data):
        super(DownloadStruct, self).__init__(client, data)
        self.sha1 = data.get('sha1', None)
        self.name = data.get('name', None)
        self.message = data.get('message', None)
        self.url = Url(client, data.get('url', {}))
        self.external_link = data.get('external_link', None)
        self.recommend_bittorrent = data.get('recommend_bittorrent', None)
        self.human_size = data.get('human_size', None)
        self.file_size = data.get('file_size', None)
        self.md5 = data.get('md5', None)
        self.fat32_warning = data.get('fat32_warning', None)
        self.size = data.get('size', None)
        self.small = data.get('small', None)


class Url(BaseModel):
    def __init__(self, client, data):
        super(Url, self).__init__(client, data)
        self.web = data.get('web', None)
        self.bittorrent = data.get('bittorrent', None)


class Price(BaseModel):
    def __init__(self, client, data):
        super(Price, self).__init__(client, data)
        self.value = data[0]
        self.currency = data[1]

    def __cmp__(self, other):
        if other.currency == self.currency:
            if self.value < other.value:
                return -1
            elif self.value > other.value:
                return 1
            else:
                return 0
        else:
            raise NotImplemented("Mixed currencies cannot be compared")

    def __repr__(self):
        return "Price: <{value:.2f}{currency}>".format(value=self.value,
                                                       currency=self.currency)
