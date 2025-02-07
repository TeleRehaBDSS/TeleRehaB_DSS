import multiprocessing
import numpy as np
from pyqtgraph import ColorMap
from PyQt5 import QtWidgets
import pyqtgraph as pg
from configuration import config
from create_walking_path import get_treadmill_information
import cv2
from scipy.ndimage import zoom
from scipy.ndimage import gaussian_filter
from centroids_detection import update_foot_centroids


# Configuration
rows = config['ROWS']
cols = config['COLS']

# Initialize the multiprocessing queue
data_queue = multiprocessing.Queue()
visual_queue = multiprocessing.Queue()

mats_for_treadmill = get_treadmill_information()

# Create treadmill matrix dimensions
treadmill_rows = rows
treadmill_cols = cols * len(mats_for_treadmill)

# Create z_data_last for single and multiple mats
z_data_last_single = np.zeros((rows, cols))
z_data_last_treadmill = np.zeros((treadmill_rows, treadmill_cols ))

# Widget for a single mat data_queue
class PressureMapAppSingle(QtWidgets.QMainWindow):

    def __init__(self, data_queue):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle(f'{rows}x{cols} - Data Visualization')
        # Create the main widget
        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        
        # Create a layout
        layout = QtWidgets.QVBoxLayout(self.main_widget)

        # Create the image view widget for displaying the heatmap
        self.image_view = pg.ImageView()

        # Hide extrabuttons and histogram from heatmap
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        self.image_view.ui.histogram.hide()

        layout.addWidget(self.image_view)

        # Create a colorful colormap
        colors = [
            (0, 0, 255),  # Blue
            (0, 255, 255),  # Cyan
            (0, 255, 0),  # Green
            (255, 255, 0),  # Yellow
            (255, 0, 0),  # Red
        ]
        cmap = ColorMap(pos=np.linspace(0.0, 1.0, len(colors)), color=colors)
        lut = cmap.getLookupTable(0.0, 1.0, 256)

        # Set the colormap to the ImageView
        self.image_view.setColorMap(cmap)

        # Hide extra buttons and histogram from heatmap
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        self.image_view.ui.histogram.hide()

        # Create scatter plot items for the right and left foot
        #self.right_foot_item = pg.ScatterPlotItem(pen=pg.mkPen(None), brush='b', size=10)
        #self.left_foot_item = pg.ScatterPlotItem(pen=pg.mkPen(None), brush='r', size=10)

        # Add the scatter plot items to the view
        #self.image_view.addItem(self.right_foot_item)
        #self.image_view.addItem(self.left_foot_item)

        # Set up a timer to refresh the display
        self.timer = pg.QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_single_heatmap)      
        self.timer.start(5)  # Update every 100 milliseconds (0.1 seconds)

        self.show()
    
    def update_single_heatmap(self):

        global z_data_last_single
        
        try:
            z_data = data_queue.get_nowait()  # Non-blocking get
            z_data_last_single = z_data
        except:
            z_data = z_data_last_single

        # Update the image view with the new data
        z_data = np.array(z_data)
        #right_foot, left_foot = update_foot_centroids(z_data)
        # Upscale using OpenCV
        #scale_factor = 4
        #high_res_matrix = cv2.resize(z_data, (48*scale_factor, 48*scale_factor), interpolation=cv2.INTER_CUBIC)
        high_res_matrix = zoom(z_data, 1, order=3)
        high_res_matrix_smooth = gaussian_filter(high_res_matrix, sigma=0.35)
        self.image_view.setImage(high_res_matrix_smooth, autoLevels=True)
        # Update scatter plot for foot centroids
        # Prepare data for scatter plot items
        #right_foot_data = []
        #left_foot_data = []
"""
        if not np.isnan(right_foot).any():
            right_foot_data = [(right_foot[0], right_foot[1])]
    
        if not np.isnan(left_foot).any():
            left_foot_data = [(left_foot[0], left_foot[1])]

        # Update scatter plot items
        self.right_foot_item.setData(pos=right_foot_data, brush='black', size=25)
        self.left_foot_item.setData(pos=left_foot_data, brush='r', size=25)
"""
# Widget for walking path data_queue           
class PressureMapAppTreadmill(QtWidgets.QMainWindow):
     
    def __init__(self, visual_queue):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Data Visualization')
        # Create the main widget
        self.main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.main_widget)
        
        # Create a layout
        layout = QtWidgets.QVBoxLayout(self.main_widget)

        # Create the image view widget for displaying the heatmap
        self.image_view = pg.ImageView()
        layout.addWidget(self.image_view)

        # Create a colorful colormap
        colors = [
            (0, 0, 255),  # Blue
            (0, 255, 255),  # Cyan
            (0, 255, 0),  # Green
            (255, 255, 0),  # Yellow
            (255, 0, 0),  # Red
        ]
        cmap = ColorMap(pos=np.linspace(0.0, 1.0, len(colors)), color=colors)
        lut = cmap.getLookupTable(0.0, 1.0, 256)

        # Set the colormap to the ImageView
        self.image_view.setColorMap(cmap)

        # Hide extra buttons and histogram from heatmap
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        self.image_view.ui.histogram.hide()

        # Set up a timer to refresh the display
        self.timer = pg.QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_treadmill_heatmap)
        self.timer.start(5)  # Update every 100 milliseconds (0.1 seconds)

        self.show()


    def update_treadmill_heatmap(self):

        global z_data_last_treadmill

        try:
            z_data = visual_queue.get_nowait()  # Non-blocking get
            z_data_last_treadmill = z_data
            while not visual_queue.empty():
                visual_queue.get()
        except:
            z_data = z_data_last_treadmill

        # Update the image view with the new data
        z_data = np.array(z_data)

        self.image_view.setImage(z_data, autoLevels=True)
