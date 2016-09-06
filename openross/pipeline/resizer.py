from twisted.internet import defer, threads
from twisted.python import log
from datetime import datetime
from utils import time_on_statsd, statsd_name
from image_modes import process_image_with_mode
from pgmagick import Image, CompositeOperator as co
import pgmagick as pg
import settings
import logging


class Resizer(object):
    """ Pipeline process which takes an image and resizes using a given image mode """

    def __init__(self, engine):
        self.engine = engine

    def _resize_using_pg(self, image, width, height, mode, sbd_id):
        """ Resize using image mode. """

        blob = pg.Blob(image)
        blob_out = pg.Blob()
        img = pg.Image(blob)
        img.filterType(pg.FilterTypes.LanczosFilter)

        img = process_image_with_mode(img, width, height, mode)


        if sbd_id in ["4398", "2456", "1976", "616", "536"]:
            layer = Image('/home/ubuntu/{}.png'.format(sbd_id))
        else:
            layer = Image('/home/ubuntu/DEFAULT.png')

        layer = process_image_with_mode(layer, width, height, mode)

        img.composite(layer, 0, 0, co.OverCompositeOp)

        # Image should be repaged after a crop/resize
        img.page(pg.Geometry(0, 0, 0, 0))
        if settings.IMAGE_QUALITY is not None:  # May be handled by custom mode
            img.quality(settings.IMAGE_QUALITY)

        img.write(blob_out, 'JPEG')
        return blob_out.data, img.size().width(), img.size().height()

    @time_on_statsd(statsd_name(), 'resizer')
    @defer.inlineCallbacks
    def process_image(self, payload, **kwargs):
        """ Resizes image to given parameters """

        # If original path given, don't resize
        if 'skip_resize' in payload.keys():
            payload['image'] = payload['original_image']
            defer.returnValue(payload)

        data, w, h = yield threads.deferToThread(
            self._resize_using_pg, payload['original_image'], payload['width'],
            payload['height'], payload['mode'], payload['image_path'].split('/')[0]
        )

        if settings.DEBUG:
            log.msg(
                "[%s] Resized Image Size %s" % (datetime.now().isoformat(), len(data)),
                logLevel=logging.DEBUG
            )
        payload['image'] = data
        payload['resized_width'] = w
        payload['resized_height'] = h

        defer.returnValue(payload)
