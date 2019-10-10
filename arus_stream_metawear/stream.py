import logging
import time

import pandas as pd
import numpy as np
from arus.core.stream import Stream
from arus.libs.date import parse_timestamp
from mbientlab.metawear import cbindings, libmetawear
from pymetawear.client import MetaWearClient

from .corrector import MetawearTimestampCorrector


class MetawearStream(Stream):
    """Data stream to syncly or asyncly load real-time data from a metawear device

    This class inherits `Stream` class to load metawear device data coming in real-time.

    Examples:
        1. Loading a metawear device as dataframe every 10 seconds asynchronously and print out the head of each one.

        ```python
        addr = "D2:C6:AF:2B:DB:22"
        stream = MetawearStream(data_source=addr, sr=50,
                                grange=8, chunk_size=10, name='metawear-stream')
        stream.start(scheduler='thread')
        for data in stream.get_iterator():
            print(data.head())
        ```
    """

    def __init__(self, data_source, sr=50, grange=8, chunk_size=10, session_begin=None, name='metawear-stream'):
        """
        Args:
            data_source (str): mac address of the metawear device.
            sr (int): the sampling rate (Hz) to be set for the given device.
            grange (int): the dynamice range (g) to be set for the given device.
            chunk_size (int): the chunk size in seconds to load data in the iterator each time.
            session_begin (float, int, datetime, datetime64, or str): the common start time used to segment chunks. This is used when there are multiple devices and you want to synchronize between them. If it is `None`, we will use the stream's first timestamp instead.
            name (str, optional): see `Stream.name`.
        """
        super().__init__(data_source=data_source, name=name)
        session_begin_ts = parse_timestamp(session_begin)
        self._sr = sr
        self._grange = grange
        self._chunk_size = chunk_size
        self._device = None
        self._corrector = MetawearTimestampCorrector(sr)
        self._chunk_buffer = []
        self._chunk_boundary = np.floor(session_begin_ts.timestamp())
        self._chunk_sample_count = 0
        if self._chunk_boundary is not None:
            logging.info('Use session begin time:' +
                         session_begin_ts.strftime("%Y-%m-%d %H:%M:%S"))

    def get_device_name(self):
        model_code = libmetawear.mbl_mw_metawearboard_get_model(
            self._device.mw.board)
        metawear_models = cbindings.Model()
        model_names = list(
            filter(lambda attr: '__' not in attr, dir(metawear_models)))
        for name in model_names:
            if getattr(metawear_models, name) == model_code:
                return name
        return 'NA'

    def _setup_metawear(self, addr):
        try:
            self._device = MetaWearClient(addr, connect=True, debug=False)
            self._device_name = self.get_device_name()
        except Exception as e:
            logging.error(str(e))
            logging.info('Retry connect to ' + addr)
            time.sleep(1)
        logging.info("New metawear connected: {0}".format(
            self._device))
        # high frequency throughput connection setup
        self._device.settings.set_connection_parameters(
            7.5, 7.5, 0, 6000)
        # Up to 4dB for Class 2 BLE devices
        # https://github.com/hbldh/pymetawear/blob/master/pymetawear/modules/settings.py
        # https://mbientlab.com/documents/metawear/cpp/0/settings_8h.html#a335f712d5fc0587eff9671b8b105d3ed
        # Hossain AKMM, Soh WS. A comprehensive study of Bluetooth signal parameters for localization. 2007 Ieee 18th International Symposium on Personal, Indoor and Mobile Radio Communications, Vols 1-9. 2007:428-32.
        self._device.settings.set_tx_power(power=4)

        self._device.accelerometer.set_settings(
            data_rate=self._sr, data_range=self._grange)
        self._device.accelerometer.high_frequency_stream = True

    def _start_metawear(self):
        def _start():
            logging.info('starting accelerometer module...')
            self._device.accelerometer.notifications(
                callback=self._pack_and_send_data)
        _start()
        return self

    def _pack_and_send_data(self, data):
        package = self._pack_data(data)
        if self._chunk_boundary is None:
            self._chunk_boundary = np.floor(package['ts_withloss'])
        if package['ts_withloss'] < self._chunk_boundary:
            # discard samples in the past
            return
        if package['ts_withloss'] - self._chunk_boundary >= self._chunk_size and len(self._chunk_buffer) == 0:
            # adjust chunk window to match the closest sample
            n_chunks = int((package['ts_withloss'] -
                            self._chunk_boundary) / self._chunk_size)
            self._chunk_boundary += n_chunks * self._chunk_size
        if package['ts_withloss'] - self._chunk_boundary >= self._chunk_size:
            df = self._format_chunk(self._chunk_buffer)
            self._chunk_boundary += self._chunk_size
            self._chunk_buffer = []
            self._put_data_in_queue(df)
        package['ts_withloss'] = pd.Timestamp.fromtimestamp(
            package['ts_withloss'])
        package['ts_noloss'] = pd.Timestamp.fromtimestamp(
            package['ts_noloss'])
        package['ts_nofix'] = pd.Timestamp.fromtimestamp(
            package['ts_nofix'])
        package['ts_realworld'] = pd.Timestamp.fromtimestamp(
            package['ts_realworld'])
        self._chunk_buffer.append(package)

    def _calibrate_coord_system(self, data):
        # axis values are calibrated according to the coordinate system of Actigraph GT9X
        # http://www.correctline.pl/wp-content/uploads/2015/01/ActiGraph_Device_Axes_Link.png
        x = data['value'].x
        y = data['value'].y
        z = data['value'].z
        if self._device_name == 'METAMOTION_R':
            # as normal wear in the case on wrist
            calibrated_x = y
            calibrated_y = -x
            calibrated_z = z
        else:
            calibrated_x = x
            calibrated_y = y
            calibrated_z = z
        return (calibrated_x, calibrated_y, calibrated_z)

    def _pack_data(self, data):
        real_world_ts = time.time()
        ts_set = self._corrector.correct(data, real_world_ts)
        calibrated_values = self._calibrate_coord_system(data)
        package = {
            'index': self._chunk_sample_count,
            'mac_address': self._data_source,
            'stream_name': self.name,
            'device_name': self._device_name,
            'data_type': "accel",
            'ts_realworld': real_world_ts,
            'ts_nofix': ts_set[0],
            'ts_noloss': ts_set[1],
            'ts_withloss': ts_set[2],
            'x': calibrated_values[0],
            'y': calibrated_values[1],
            'z': calibrated_values[2]}
        self._chunk_sample_count += 1
        return package

    def _format_chunk(self, chunk_buffer):
        df = pd.DataFrame(data=self._chunk_buffer)
        df = df[['ts_withloss', 'x', 'y', 'z',
                 'index', 'mac_address', 'stream_name', 'device_name', 'data_type', 'ts_realworld', 'ts_nofix', 'ts_noloss']]
        df.columns = ['HEADER_TIME_STAMP', 'X', 'Y', 'Z', 'INDEX', 'SOURCE', 'STREAM_NAME',
                      'SENSOR_TYPE', 'DATA_TYPE', 'TIME_STAMP_REAL', 'TIME_STAMP_ORIGINAL', 'TIME_STAMP_NOLOSS']
        df.insert(len(df.columns), 'TIME_STAMP_CHUNK_BEGIN',
                  pd.Timestamp.fromtimestamp(self._chunk_boundary))
        return df

    def _load_metawear(self, addr):
        self._setup_metawear(addr)
        self._start_metawear()

    def load_(self, obj_toload):
        if isinstance(obj_toload, str):
            addr = obj_toload
            self._load_metawear(addr)
        else:
            raise RuntimeError(
                "Data source should be the mac address of the metawear device")
