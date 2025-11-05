from datetime import datetime, timedelta
import time


class RateLimitConfig:
    def __init__(self, threshold_in_milliseconds: int = 100):
        self.threshold_in_milliseconds = threshold_in_milliseconds
        self.threshold_in_microseconds = threshold_in_milliseconds * 1000
        self.threshold_in_seconds = threshold_in_milliseconds / 1000
        self.last_successful_request_timestamp = datetime.now()

    def rate_limit(self) -> None:
        if self.should_rate_limit():
            time.sleep(self.threshold_in_seconds)
        self.update_last_successful_request_timestamp()

    def should_rate_limit(self) -> bool:
        return (datetime.now() - self.last_successful_request_timestamp) < timedelta(
            microseconds=self.threshold_in_microseconds
        )

    def update_last_successful_request_timestamp(self) -> None:
        self.last_successful_request_timestamp = datetime.now()

    def get_threshold_in_seconds(self) -> float:
        return self.threshold_in_seconds

    def get_threshold_in_microseconds(self) -> int:
        return self.threshold_in_microseconds

    def get_threshold_in_milliseconds(self) -> int:
        return self.threshold_in_milliseconds

    def get_last_successful_request_timestamp(self) -> datetime:
        return self.last_successful_request_timestamp
