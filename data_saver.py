"""
Handles saving acquired data to an Excel file.
"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

class DataSaver:
    """
    Handles saving acquired data to an Excel file.
    """
    def __init__(self, filename="pico_stream_output.xlsx"):
        """
        Initializes the DataSaver with a default filename.

        Args:
            filename (str): The name of the Excel file to save.
        """
        self.filename = filename

    def save_to_excel(self, plot_data):
        """
        Saves a list of data rows to an Excel workbook.

        Args:
            plot_data (list): A list of tuples, where each tuple is a row of data.
        """
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "PicoScope Data"
            
            # Write header with styling
            header_font = Font(bold=True)
            ws.append(["Time (ms)", "Voltage Channel A (mV)", "Voltage Channel B (mV)"])
            for cell in ws[1]:
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center')
            
            # Write data
            for row in plot_data:
                ws.append(list(row))
            
            # Adjust column widths
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter # Get the column letter
                for cell in col:
                    try: # Necessary to avoid error on empty cells
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws.column_dimensions[column].width = adjusted_width
                
            wb.save(self.filename)
            print(f"Excel file '{self.filename}' saved successfully.")
        except Exception as e:
            print(f"Error saving to Excel: {e}")
