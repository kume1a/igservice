import logging
from urllib.parse import urlparse

import requests
# from requests.packages.urllib3.exceptions import InsecureRequestWarning

from src.instagrapi.mixins.account import AccountMixin
from src.instagrapi.mixins.album import DownloadAlbumMixin, UploadAlbumMixin
from src.instagrapi.mixins.auth import LoginMixin
from src.instagrapi.mixins.bloks import BloksMixin
from src.instagrapi.mixins.challenge import ChallengeResolveMixin
from src.instagrapi.mixins.clip import DownloadClipMixin, UploadClipMixin
from src.instagrapi.mixins.collection import CollectionMixin
from src.instagrapi.mixins.comment import CommentMixin
from src.instagrapi.mixins.direct import DirectMixin
from src.instagrapi.mixins.explore import ExploreMixin
from src.instagrapi.mixins.fbsearch import FbSearchMixin
from src.instagrapi.mixins.fundraiser import FundraiserMixin
from src.instagrapi.mixins.hashtag import HashtagMixin
from src.instagrapi.mixins.highlight import HighlightMixin
from src.instagrapi.mixins.igtv import DownloadIGTVMixin, UploadIGTVMixin
from src.instagrapi.mixins.insights import InsightsMixin
from src.instagrapi.mixins.location import LocationMixin
from src.instagrapi.mixins.media import MediaMixin
from src.instagrapi.mixins.multiple_accounts import MultipleAccountsMixin
from src.instagrapi.mixins.note import NoteMixin
from src.instagrapi.mixins.notification import NotificationMixin
from src.instagrapi.mixins.password import PasswordMixin
from src.instagrapi.mixins.photo import DownloadPhotoMixin, UploadPhotoMixin
from src.instagrapi.mixins.private import PrivateRequestMixin
from src.instagrapi.mixins.public import (
    ProfilePublicMixin,
    PublicRequestMixin,
    TopSearchesPublicMixin,
)
from src.instagrapi.mixins.share import ShareMixin
from src.instagrapi.mixins.signup import SignUpMixin
from src.instagrapi.mixins.story import StoryMixin
from src.instagrapi.mixins.timeline import ReelsMixin
from src.instagrapi.mixins.totp import TOTPMixin
from src.instagrapi.mixins.track import TrackMixin
from src.instagrapi.mixins.user import UserMixin
from src.instagrapi.mixins.video import DownloadVideoMixin, UploadVideoMixin

# requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Used as fallback logger if another is not provided.
DEFAULT_LOGGER = logging.getLogger("instagrapi")


class Client(
    PublicRequestMixin,
    ChallengeResolveMixin,
    PrivateRequestMixin,
    TopSearchesPublicMixin,
    ProfilePublicMixin,
    LoginMixin,
    ShareMixin,
    TrackMixin,
    FbSearchMixin,
    HighlightMixin,
    DownloadPhotoMixin,
    UploadPhotoMixin,
    DownloadVideoMixin,
    UploadVideoMixin,
    DownloadAlbumMixin,
    NotificationMixin,
    UploadAlbumMixin,
    DownloadIGTVMixin,
    UploadIGTVMixin,
    MediaMixin,
    UserMixin,
    InsightsMixin,
    CollectionMixin,
    AccountMixin,
    DirectMixin,
    LocationMixin,
    HashtagMixin,
    CommentMixin,
    StoryMixin,
    PasswordMixin,
    SignUpMixin,
    DownloadClipMixin,
    UploadClipMixin,
    ReelsMixin,
    ExploreMixin,
    BloksMixin,
    TOTPMixin,
    MultipleAccountsMixin,
    NoteMixin,
    FundraiserMixin,
):
    proxy = None

    def __init__(
        self,
        settings: dict = {},
        proxy: str = None,
        delay_range: list = None,
        logger=DEFAULT_LOGGER,
        **kwargs,
    ):

        super().__init__(**kwargs)

        self.settings = settings
        self.logger = logger
        self.delay_range = delay_range

        self.set_proxy(proxy)

        self.init()

    def set_proxy(self, dsn: str):
        if dsn:
            assert isinstance(
                dsn, str
            ), f'Proxy must been string (URL), but now "{dsn}" ({type(dsn)})'
            self.proxy = dsn
            proxy_href = "{scheme}{href}".format(
                scheme="http://" if not urlparse(self.proxy).scheme else "",
                href=self.proxy,
            )
            self.public.proxies = self.private.proxies = {
                "http": proxy_href,
                "https": proxy_href,
            }
            return True
        self.public.proxies = self.private.proxies = {}
        return False
