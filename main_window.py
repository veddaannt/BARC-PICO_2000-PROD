"""
Defines the main window for the Picoscope data acquisition GUI.
"""
import sys
import collections
import numpy as np
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QPushButton, 
                             QHBoxLayout, QLabel, QLineEdit, QFormLayout, QGroupBox,
                             QMessageBox)
from PyQt5.QtCore import QThread, QTimer, pyqtSignal, QObject
from pyqtgraph import PlotWidget, mkPen
from picoscope_handler import PicoScopeWorker
from data_saver import DataSaver

class MainWindow(QMainWindow):
    """
    The main application window, containing the GUI and logic for data acquisition.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Picoscope Streaming GUI")
        self.setGeometry(100, 100, 1200, 800)

        self.pico_thread = None
        self.pico_worker = None
        self.data_saver = DataSaver()
        self.all_data = []
        self.total_samples_acquired = 0
        self.is_running = False

        # --- Data Queues for Plotting ---
        # Define the plot window size in milliseconds
        self.plot_window_ms = 200.0
        # Placeholder for actual sample interval
        self.sample_interval_us = 10 
        self.deque_size = int(self.plot_window_ms / (self.sample_interval_us * 1e-3))
        self.chA_deque = collections.deque(maxlen=self.deque_size)
        self.chB_deque = collections.deque(maxlen=self.deque_size)
        self.time_deque = collections.deque(maxlen=self.deque_size)

        self.setup_ui()

    def setup_ui(self):
        """
        Sets up the graphical user interface elements.
        """
        # Central Widget and Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Controls Layout
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)

        # Controls Group Box
        controls_group_box = QGroupBox("Controls")
        controls_layout.addWidget(controls_group_box)
        controls_form_layout = QFormLayout(controls_group_box)

        # Input fields
        self.sample_interval_input = QLineEdit("10")
        controls_form_layout.addRow("Sample Interval (µs):", self.sample_interval_input)
        
        self.max_samples_input = QLineEdit("50000")
        controls_form_layout.addRow("Max Samples:", self.max_samples_input)
        
        self.oversampling_input = QLineEdit("1")
        controls_form_layout.addRow("Oversampling:", self.oversampling_input)
        
        self.channel_range_input = QLineEdit("9")
        controls_form_layout.addRow("Channel Range:", self.channel_range_input)
        
        # Buttons
        self.start_button = QPushButton("Start Acquisition")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_button.clicked.connect(self.start_acquisition)
        controls_form_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop Acquisition")
        self.stop_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.stop_button.setEnabled(False)
        controls_form_layout.addWidget(self.stop_button)
        
        self.save_button = QPushButton("Save Data to Excel")
        self.save_button.setStyleSheet("background-color: #2196F3; color: white;")
        self.save_button.clicked.connect(self.save_data)
        controls_form_layout.addWidget(self.save_button)
        
        # Status Group Box
        status_group_box = QGroupBox("Status")
        controls_layout.addWidget(status_group_box)
        status_layout = QFormLayout(status_group_box)
        
        self.time_label = QLabel("Time: 0.00 ms")
        self.voltage_a_label = QLabel("Voltage A: 0.00 mV")
        self.voltage_b_label = QLabel("Voltage B: 0.00 mV")
        self.samples_label = QLabel("Total Samples: 0")
        
        status_layout.addRow("Current Time:", self.time_label)
        status_layout.addRow("Voltage A:", self.voltage_a_label)
        status_layout.addRow("Voltage B:", self.voltage_b_label)
        status_layout.addRow("Total Samples:", self.samples_label)

        # Plot Widget
        self.plot_widget = PlotWidget()
        self.plot_widget.setLabel('left', "Voltage", units='mV')
        self.plot_widget.setLabel('bottom', "Time", units='ms')
        self.plot_widget.setTitle("Real-time Picoscope Data")
        self.plot_widget.addLegend()
        self.plot_widget.showGrid(x=True, y=True)
        main_layout.addWidget(self.plot_widget)

        # Plot curves
        self.curve_a = self.plot_widget.plot(pen=mkPen('b', width=2), name="Channel A")
        self.curve_b = self.plot_widget.plot(pen=mkPen('r', width=2), name="Channel B")

    def start_acquisition(self):
        """
        Initializes the Picoscope worker thread and starts data acquisition.
        """
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Acquisition is already running.")
            return

        try:
            self.sample_interval_us = int(self.sample_interval_input.text())
            max_samples = int(self.max_samples_input.text())
            oversampling = int(self.oversampling_input.text())
            channel_range = int(self.channel_range_input.text())
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid input. Please enter integers.")
            return

        # Reset data for new acquisition
        self.all_data = []
        self.total_samples_acquired = 0
        self.chA_deque.clear()
        self.chB_deque.clear()
        self.time_deque.clear()
        self.deque_size = int(self.plot_window_ms / (self.sample_interval_us * 1e-3))
        self.chA_deque = collections.deque(maxlen=self.deque_size)
        self.chB_deque = collections.deque(maxlen=self.deque_size)
        self.time_deque = collections.deque(maxlen=self.deque_size)

        # Threading for data acquisition
        self.pico_thread = QThread()
        self.pico_worker = PicoScopeWorker(
            self.sample_interval_us, max_samples, oversampling, channel_range
        )
        self.pico_worker.moveToThread(self.pico_thread)

        # Connect signals and slots
        self.pico_thread.started.connect(self.pico_worker.run)
        self.pico_worker.data_acquired.connect(self.update_plot)
        self.pico_worker.finished.connect(self.on_acquisition_finished)
        self.pico_worker.error_occurred.connect(self.on_error)

        # Start the worker thread
        self.pico_thread.start()
        
        self.is_running = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        print("Acquisition started.")

    def stop_acquisition(self):
        """
        Sends a stop signal to the Picoscope worker and waits for the thread to finish.
        """
        if self.pico_worker:
            self.pico_worker.stop()
        
        # Wait for the thread to finish
        if self.pico_thread:
            self.pico_thread.quit()
            self.pico_thread.wait()

        self.is_running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        print("Acquisition stopped.")
        
    def update_plot(self, data):
        """
        Slot to receive data from the worker and update the plot and status labels.
        
        Args:
            data (tuple): A tuple containing time, chA, chB data lists.
        """
        time_data, chA_data, chB_data = data
        n_samples = len(time_data)

        if n_samples > 0:
            # Append data to the main list for later saving
            start_x_ms = self.total_samples_acquired * self.sample_interval_us * 1e-3
            for i in range(n_samples):
                time_point = time_data[i] + start_x_ms
                self.all_data.append((time_point, chA_data[i], chB_data[i]))
            
            # Append data to the deques for real-time plotting
            self.time_deque.extend(time_data)
            self.chA_deque.extend(chA_data)
            self.chB_deque.extend(chB_data)
            
            # Update plot with the deque data
            time_plot = np.arange(len(self.time_deque)) * self.sample_interval_us * 1e-3
            self.curve_a.setData(time_plot, list(self.chA_deque))
            self.curve_b.setData(time_plot, list(self.chB_deque))
            
            # Update labels with the last sample's data
            last_time = self.time_deque[-1]
            last_chA = self.chA_deque[-1]
            last_chB = self.chB_deque[-1]
            
            self.time_label.setText(f"Time: {last_time:.5f} ms")
            self.voltage_a_label.setText(f"Voltage A: {last_chA:.2f} mV")
            self.voltage_b_label.setText(f"Voltage B: {last_chB:.2f} mV")
            
            self.total_samples_acquired += n_samples
            self.samples_label.setText(f"Total Samples: {self.total_samples_acquired}")
            
    def save_data(self):
        """
        Saves all acquired data to an Excel file.
        """
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Please stop acquisition before saving.")
            return

        if not self.all_data:
            QMessageBox.information(self, "Information", "No data to save.")
            return
            
        print("Saving data to Excel...")
        self.data_saver.save_to_excel(self.all_data)
        QMessageBox.information(self, "Success", "Data saved successfully!")

    def on_acquisition_finished(self):
        """
        Slot for when the worker thread finishes.
        """
        QMessageBox.information(self, "Finished", "Data acquisition finished.")
        self.stop_acquisition()
        
    def on_error(self, message):
        """
        Slot to handle errors from the worker thread.
        """
        QMessageBox.critical(self, "Error", f"An error occurred: {message}")
        self.stop_acquisition()
        
    def closeEvent(self, event):
        """
        Handles the window close event to ensure a clean shutdown.
        """
        self.stop_acquisition()
        event.accept()
