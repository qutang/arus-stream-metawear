class MetawearTimestampCorrector(object):
    def __init__(self, sr):
        self._current_nofix_ts = None
        self._current_noloss_ts = None
        self._current_withloss_ts = None
        self._sample_interval = 1.0 / sr
        self._real_world_offset = None
        self._last_real_world_ts = None

    def _get_current_nofix_ts_in_seconds(self, data):
        return data['epoch'] / 1000.0

    def _get_real_world_offset(self, data, current_real_world_ts):
        return current_real_world_ts - \
            self._get_current_nofix_ts_in_seconds(data)

    def _apply_no_fix(self, data):
        return self._get_current_nofix_ts_in_seconds(data) + self._real_world_offset

    def _apply_fix_noloss(self, data, previous_noloss_ts):
        if previous_noloss_ts == None:
            current_noloss_ts = self._apply_no_fix(data)
        else:
            current_noloss_ts = previous_noloss_ts + self._sample_interval
        return current_noloss_ts

    def _apply_fix_withloss(self, data, previous_withloss_ts, current_real_world_ts, previous_real_world_ts):
        if previous_withloss_ts == None:
            current_withloss_ts = self._apply_fix_noloss(
                data, previous_withloss_ts)
        elif current_real_world_ts - previous_real_world_ts <= 2 * self._sample_interval:
            current_withloss_ts = self._apply_fix_noloss(
                data, previous_withloss_ts)
        elif abs(previous_withloss_ts - self._get_current_nofix_ts_in_seconds(data)) < 2 * self._sample_interval:
            # if there is no loss occuring
            current_withloss_ts = self._apply_fix_noloss(
                data, previous_withloss_ts)
        else:
            # data loss occurs
            current_nofix_ts = self._apply_no_fix(data)
            current_noloss_ts = self._apply_fix_noloss(
                data, previous_withloss_ts)
            if current_nofix_ts - current_noloss_ts > 2 * self._sample_interval:
                # late for more than two intervals, renew timestamp
                current_withloss_ts = current_nofix_ts
            else:
                current_withloss_ts = current_noloss_ts
        return current_withloss_ts

    def correct(self, data, current_real_world_ts):
        if self._real_world_offset == None:
            self._real_world_offset = self._get_real_world_offset(
                data, current_real_world_ts)
        if self._last_real_world_ts == None:
            self._last_real_world_ts = current_real_world_ts
        self._current_nofix_ts = self._apply_no_fix(data)
        self._current_noloss_ts = self._apply_fix_noloss(
            data, self._current_noloss_ts)
        self._current_withloss_ts = self._apply_fix_withloss(
            data, self._current_withloss_ts, current_real_world_ts, self._last_real_world_ts)
        diff_rw = current_real_world_ts - self._last_real_world_ts
        self._last_real_world_ts = current_real_world_ts
        return self._current_nofix_ts, self._current_noloss_ts, self._current_withloss_ts, diff_rw
