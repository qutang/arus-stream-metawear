from arus_stream_metawear.stream import MetawearStream
import logging
from datetime import datetime

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format='[%(levelname)s]%(asctime)s <P%(process)d-%(threadName)s> %(message)s')
    stream = MetawearStream("D2:C6:AF:2B:DB:22", sr=50, grange=8,
                            window_size=5, start_time=datetime.now(), name='metawear-stream')
    stream.start(scheduler='thread')
    for data in stream.get_iterator():
        print(data.head())
