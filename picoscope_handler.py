"""
Handles all communication and data acquisition with the Picoscope device,
designed for use in a separate QThread.
"""
import time
from ctypes import byref, c_int16
from picosdk.ps2000 import ps2000
from picosdk.functions import assert_pico2000_ok, adc2mV
from PyQt5.QtCore import QObject, pyqtSignal

class PicoScopeWorker(QObject):
    """
    A worker object to handle Picoscope data acquisition in a separate thread.
    Emits signals to the main GUI thread.
    """
    data_acquired = pyqtSignal(tuple)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, sample_interval_us, max_samples, oversampling, channel_range):
        super().__init__()
        self.sample_interval_us = sample_interval_us
        self.max_samples = max_samples
        self.oversampling = oversampling
        self.channel_range = channel_range
        self.running = True
        
        self.device = None
        self.handle = None
        self.buffer_a = (c_int16 * self.max_samples)()
        self.buffer_b = (c_int16 * self.max_samples)()
        self.overflow = c_int16(0)
        self.total_samples_acquired = 0
        
    def connect(self):
        """
        Connects to the Picoscope device and sets up the channels.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            self.device = ps2000.open_unit()
            self.handle = self.device.handle
            
            # Enable Channel A
            ps2000.ps2000_set_channel(self.handle, 0, True, 1, self.channel_range)
            # Enable Channel B
            ps2000.ps2000_set_channel(self.handle, 1, True, 1, self.channel_range)
            
            print("Successfully connected to Picoscope.")
            return True
        except Exception as e:
            print(f"Error connecting to Picoscope: {e}")
            self.error_occurred.emit(str(e))
            self.disconnect()
            return False

    def start_streaming(self):
        """
        Starts the streaming acquisition mode.
        """
        if self.handle:
            res = ps2000.ps2000_run_streaming(
                self.handle,
                self.sample_interval_us,
                self.oversampling,
                self.max_samples
            )
            assert_pico2000_ok(res)
            print(f"Streaming started with interval {self.sample_interval_us} µs.")
        else:
            print("Picoscope not connected. Cannot start streaming.")
            self.error_occurred.emit("Picoscope not connected. Cannot start streaming.")

    def get_data(self):
        """
        Fetches the latest data from the Picoscope.

        Returns:
            tuple: A tuple containing lists of voltage data for Channel A and Channel B,
                    and the number of samples acquired.
        """
        if not self.handle:
            return [], [], 0

        try:
            n_samples = ps2000.ps2000_get_values(
                self.handle,
                byref(self.buffer_a),
                byref(self.buffer_b),
                None,
                None,
                byref(self.overflow),
                self.max_samples
            )
        except Exception as e:
            self.error_occurred.emit(f"Error getting data: {e}")
            self.stop()
            return [], [], 0

        if n_samples > 0:
            chA_mv = adc2mV(self.buffer_a, self.channel_range, c_int16(32767))[:n_samples]
            chB_mv = adc2mV(self.buffer_b, self.channel_range, c_int16(32767))[:n_samples]
            time_data = [self.sample_interval_us * 1e-3] * n_samples # This is just for plotting relative time
            return time_data, chA_mv, chB_mv, n_samples
        return [], [], [], 0

    def disconnect(self):
        """
        Stops the streaming and closes the Picoscope connection.
        """
        if self.handle:
            ps2000.ps2000_stop(self.handle)
            self.device.close()
            print("Picoscope connection closed.")

    def run(self):
        """
        The main loop for the worker thread.
        """
        if not self.connect():
            self.finished.emit()
            return
            
        self.start_streaming()
        
        while self.running:
            time_data, chA_mv, chB_mv, n_samples = self.get_data()
            if n_samples > 0:
                self.data_acquired.emit((list(time_data), list(chA_mv), list(chB_mv)))
            time.sleep(0.01) # Small delay to prevent busy-looping
            
        self.disconnect()
        self.finished.emit()

    def stop(self):
        """
        Stops the worker thread.
        """
        self.running = False
