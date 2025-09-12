"""
Main entry point for the Picoscope data acquisition application with a PyQt5 GUI.
"""
import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow

def main():
    """
    Initializes and runs the PyQt5 application.
    """
    # Create the application instance
    app = QApplication(sys.argv)
    
    # Create the main window
    main_window = MainWindow()
    main_window.show()
    
    # Start the event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
