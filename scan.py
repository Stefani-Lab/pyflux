# -*- coding: utf-8 -*-
"""
Created on Fri Jun  1 14:18:19 2018

@author: Luciano A. Masullo
"""

import numpy as np
import time
from datetime import date, datetime
import os
import matplotlib.pyplot as plt
from matplotlib import cm
import tools.tools as tools
import ctypes as ct
from PIL import Image
from tkinter import Tk, filedialog
import tifffile as tiff
import scipy.optimize as opt

from threading import Thread

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.dockarea import Dock, DockArea
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5 import QtTest
import qdarkstyle

import drivers.ADwin as ADwin
import tools.viewbox_tools as viewbox_tools
import tools.colormaps as cmaps
from tools.lineprofile import linePlotWidget

π = np.pi


def setupDevice(adw):

    BTL = "ADwin11.btl"
    PROCESS_1 = "line_scan.TB1"
    PROCESS_2 = "moveto_xyz.TB2"
    PROCESS_3 = "actuator_z.TB3"
    PROCESS_4 = "actuator_xy.TB4"
    PROCESS_5 = "shutter.TB5"
    
    btl = adw.ADwindir + BTL
    adw.Boot(btl)

    currdir = os.getcwd()
    process_folder = os.path.join(currdir, "processes")

    process_1 = os.path.join(process_folder, PROCESS_1)
    process_2 = os.path.join(process_folder, PROCESS_2)
    process_3 = os.path.join(process_folder, PROCESS_3)
    process_4 = os.path.join(process_folder, PROCESS_4)
    process_5 = os.path.join(process_folder, PROCESS_5)
    
    adw.Load_Process(process_1)
    adw.Load_Process(process_2)
    adw.Load_Process(process_3)
    adw.Load_Process(process_4)
    adw.Load_Process(process_5)
    
    
class Frontend(QtGui.QFrame):
    
    paramSignal = pyqtSignal(dict)
    closeSignal = pyqtSignal()
    liveviewSignal = pyqtSignal(bool)
    frameacqSignal = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

#        self.device = 'simulated'
#        self.device = 'nidaq'
#        self.device = 'ADwin'

        self.roi = None
        self.lineROI = None
        self.EBPscatter = [None, None, None, None]
        self.EBPcenters = np.zeros((4, 2))
        self.advanced = False
        self.EBPshown = True
        self.fitting = False
        self.image = np.zeros((128, 128))
        
        self.initialDir = r'C:\Data'
        
        # set up GUI

        self.setup_gui()
                
        # connections between changes in parameters and emit_param function
        
        self.NofPixelsEdit.textChanged.connect(self.emit_param)
        self.scanRangeEdit.textChanged.connect(self.emit_param)
        self.pxTimeEdit.textChanged.connect(self.emit_param)
        self.initialPosEdit.textChanged.connect(self.emit_param)
        self.auxAccEdit.textChanged.connect(self.emit_param)
        self.waitingTimeEdit.textChanged.connect(self.emit_param)
        self.detectorType.activated.connect(self.emit_param)
        self.scanMode.activated.connect(self.emit_param)
        self.filenameEdit.textChanged.connect(self.emit_param)
        self.xStepEdit.textChanged.connect(self.emit_param)
        self.yStepEdit.textChanged.connect(self.emit_param)
        self.zStepEdit.textChanged.connect(self.emit_param)
        self.moveToEdit.textChanged.connect(self.emit_param)
        
    def emit_param(self):
        
        params = dict()
        
        params['detectorType'] = self.detectorType.currentText()
        params['scanType'] = self.scanMode.currentText()
        params['scanRange'] = float(self.scanRangeEdit.text())
        params['NofPixels'] = int(self.NofPixelsEdit.text())
        params['pxTime'] = float(self.pxTimeEdit.text())
        params['initialPos'] = np.array(self.initialPosEdit.text().split(' '),
                                        dtype=np.float64)
        params['a_aux_coeff'] = np.array(self.auxAccEdit.text().split(' '),
                                              dtype=np.float32)/100
        
        params['waitingTime'] = int(self.waitingTimeEdit.text())  # in µs
        params['fileName'] = os.path.join(self.folderEdit.text(),
                                          self.filenameEdit.text())
        params['moveToPos'] = np.array(self.moveToEdit.text().split(' '),
                                       dtype=np.float16)
        
        params['xStep'] = float(self.xStepEdit.text())
        params['yStep'] = float(self.yStepEdit.text())
        params['zStep'] = float(self.zStepEdit.text())
#        params['Nframes'] = float(self.NframesEdit.text())

        self.paramSignal.emit(params)
        
    @pyqtSlot(dict)
    def get_backend_param(self, params):
        
        frameTime = params['frameTime']
        pxSize = params['pxSize']
        maxCounts = params['maxCounts']
        initialPos = params['initialPos']
        
#        print(initialPos)
        
        self.frameTimeValue.setText('{}'.format(np.around(frameTime, 2)))
        self.pxSizeValue.setText('{}'.format(np.around(1000 * pxSize, 3))) # in nm
        self.maxCountsValue.setText('{}'.format(maxCounts)) 
        self.initialPosEdit.setText('{} {} {}'.format(*initialPos))
        
        self.pxSize = pxSize
     
    @pyqtSlot(np.ndarray)
    def get_image(self, image):
        
        self.img.setImage(image, autoLevels=False)
        self.image = image
    
    def toggle_advanced(self):
        
        if self.advanced:
            
            self.auxAccelerationLabel.show()
            self.auxAccEdit.show()
            self.waitingTimeLabel.show()
            self.waitingTimeEdit.show() 
            self.preview_scanButton.show()
            
            self.advanced = False
            
        else:
            
            self.auxAccelerationLabel.hide()
            self.auxAccEdit.hide()
            self.waitingTimeLabel.hide()
            self.waitingTimeEdit.hide() 
            self.preview_scanButton.hide()
            
            self.advanced = True

    def load_folder(self):

        try:
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(parent=root,
                                             initialdir=self.initialDir)
            root.destroy()
            if folder != '':
                self.folderEdit.setText(folder)
        except OSError:
            pass
        
#            
#    def xMoveUp(self):
#        
#        newPos_µm = self.initialPos[0] - self.xStep
#        newPos_µm = round(newPos_µm, 3)
#        self.initialPosEdit.setText('{} {} {}'.format(newPos_µm,
#                                                      self.initialPos[1],
#                                                      self.initialPos[2]))
#        
#    def xMoveDown(self):
#        
#        newPos_µm = self.initialPos[0] + self.xStep
#        newPos_µm = np.around(newPos_µm, 3)
#        self.initialPosEdit.setText('{} {} {}'.format(newPos_µm,
#                                                      self.initialPos[1],
#                                                      self.initialPos[2]))
    
#    def yMoveUp(self):
#        
#        newPos_µm = self.initialPos[1] + self.yStep
#        newPos_µm = np.around(newPos_µm, 3)       
#        self.initialPosEdit.setText('{} {} {}'.format(self.initialPos[0],
#                                                      newPos_µm,
#                                                      self.initialPos[2]))
    
#    def yMoveDown(self):
#        
#        newPos_µm = self.initialPos[1] - self.yStep
#        newPos_µm = np.around(newPos_µm, 3)
#        self.initialPosEdit.setText('{} {} {}'.format(self.initialPos[0],
#                                                      newPos_µm,
#                                                      self.initialPos[2]))

#    def zMoveUp(self):
#        
#        newPos_µm = self.initialPos[2] + self.zStep
#        newPos_µm = np.around(newPos_µm, 3)
#        self.initialPosEdit.setText('{} {} {}'.format(self.initialPos[0],
#                                                      self.initialPos[1],
#                                                      newPos_µm))
        
#    def zMoveDown(self):
#        
#        newPos_µm = self.initialPos[2] - self.zStep
#        newPos_µm = np.around(newPos_µm, 3)
#        self.initialPosEdit.setText('{} {} {}'.format(self.initialPos[0],
#                                                      self.initialPos[1],
#                                                      newPos_µm))
    
    def preview_scan(self):

        plt.figure('Preview scan plot x vs t')
        plt.plot(self.data_t_adwin[0:-1], self.data_x_adwin, 'go')
        plt.xlabel('t (ADwin time)')
        plt.ylabel('V (DAC units)')

        if np.max(self.data_x_adwin) > 2**16:

            plt.plot(self.data_t_adwin[0:-1],
                     2**16 * np.ones(np.size(self.data_t_adwin[0:-1])), 'r-')

    def toggle_liveview(self):

        if self.liveviewButton.isChecked():
            self.liveviewSignal.emit(True)
            
            if self.roi is not None:

                self.vb.removeItem(self.roi)
                self.roi.hide()
    
                self.ROIButton.setChecked(False)
            
            if self.lineROI is not None:

                self.vb.removeItem(self.lineROI)
                self.lplotWidget.hide()
                self.lineProfButton.setChecked(False)
                self.lineROI = None

            else:
    
                pass

        else:
            self.liveviewSignal.emit(False)   
            
    def toggle_frame_acq(self):

        if self.acquireFrameButton.isChecked():
            self.frameacqSignal.emit(True)
            
            if self.roi is not None:

                self.vb.removeItem(self.roi)
                self.roi.hide()
    
                self.ROIButton.setChecked(False)
                self.liveviewButton.setChecked(False)
            
            if self.lineROI is not None:

                self.vb.removeItem(self.lineROI)
                self.lplotWidget.hide()
                self.lineProfButton.setChecked(False)
                self.lineROI = None

            else:
    
                pass

        else:
            self.frameacqSignal.emit(False)   

    def line_profile(self):
        
        if self.lineROI is None:
            
            self.lineROI = pg.LineSegmentROI([[10, 64], [120,64]], pen='r')
            self.vb.addItem(self.lineROI)
            
            self.lplotWidget.show()
            
        else:

            self.vb.removeItem(self.lineROI)
            
            self.lineROI = pg.LineSegmentROI([[10, 64], [120,64]], pen='r')
            self.vb.addItem(self.lineROI)
            
        self.lineROI.sigRegionChanged.connect(self.update_line_profile)
        
    def update_line_profile(self):
        
        data = self.lineROI.getArrayRegion(self.image, self.img)
        self.lplotWidget.linePlot.clear()
        x = self.pxSize * np.arange(np.size(data))*1000
        self.lplotWidget.linePlot.plot(x, data)
        
    def toggle_ROI(self):
        
        ROIpen = pg.mkPen(color='y')
        npixels = int(self.NofPixelsEdit.text())

        if self.roi is None:

            ROIpos = (0.5 * npixels - 64, 0.5 * npixels - 64)
            self.roi = viewbox_tools.ROI(npixels/2, self.vb, ROIpos,
                                         handlePos=(1, 0),
                                         handleCenter=(0, 1),
                                         scaleSnap=True,
                                         translateSnap=True,
                                         pen=ROIpen)

        else:

            self.vb.removeItem(self.roi)
            self.roi.hide()

            ROIpos = (0.5 * npixels - 64, 0.5 * npixels - 64)
            self.roi = viewbox_tools.ROI(npixels/2, self.vb, ROIpos,
                                         handlePos=(1, 0),
                                         handleCenter=(0, 1),
                                         scaleSnap=True,
                                         translateSnap=True,
                                         pen=ROIpen)
            
        if self.EBProiButton.isChecked:
            self.EBProiButton.setChecked(False)
            
    def select_ROI(self):

        self.liveviewSignal.emit(False)
        
        ROIsize = np.array(self.roi.size())
        ROIpos = np.array(self.roi.pos())
        
        npixels = int(self.NofPixelsEdit.text())
        pxSize = self.pxSize
        initialPos = np.array(self.initialPosEdit.text().split(' '),
                              dtype=np.float64)

        newPos_px = tools.ROIscanRelativePOS(ROIpos, npixels, ROIsize[1])

        newPos_µm = newPos_px * pxSize + initialPos[0:2]

        newPos_µm = np.around(newPos_µm, 2)

        self.initialPosEdit.setText('{} {} {}'.format(newPos_µm[0],
                                                      newPos_µm[1],
                                                      initialPos[2]))

        newRange_px = ROIsize[1]
        newRange_µm = pxSize * newRange_px
        newRange_µm = np.around(newRange_µm, 2)
        self.scanRangeEdit.setText('{}'.format(newRange_µm))
        
        self.emit_param()
        
        
    def set_EBP(self):
        
        pxSize = self.pxSize
        ROIsize = np.array(self.roi.size())
        
        for i in range(4):
        
            if self.EBPscatter[i] is not None:
                
                self.vb.removeItem(self.EBPscatter[i])
        
#        array = self.roi.getArrayRegion(self.scworker.image, self.img)
        ROIsize = np.array(self.roi.size())
        ROIpos_µm = np.array(self.roi.pos()) * pxSize
            
        xmin = ROIpos_µm[0]
        xmax = ROIpos_µm[0] + ROIsize[0] * pxSize
        
        ymin = ROIpos_µm[1]
        ymax = ROIpos_µm[1] + ROIsize[1] * pxSize
        
        x0 = (xmax+xmin)/2
        y0 = (ymax+ymin)/2
        
        if self.EBPtype.currentText() == 'triangle':
        
            L = int(self.LEdit.text())/1000 # in µm
            θ = π * np.array([1/6, 5/6, 3/2])
            ebp = (L/2)*np.array([[0, 0], [np.cos(θ[0]), np.sin(θ[0])], 
                                 [np.cos(θ[1]), np.sin(θ[1])], 
                                 [np.cos(θ[2]), np.sin(θ[2])]])
            
            self.EBP = (ebp + np.array([x0, y0]))/pxSize
                                       
        print('[scan] EBP px', self.EBP)
            
        for i in range(4):
        
            if i == 0:
                mybrush = pg.mkBrush(255, 255, 0, 255)
                
            if i == 1:
                mybrush = pg.mkBrush(255, 127, 80, 255)
                
            if i == 2:
                mybrush = pg.mkBrush(135, 206, 235, 255)
                
            if i == 3:
                mybrush = pg.mkBrush(0, 0 ,0 , 255)
                
            self.EBPscatter[i] = pg.ScatterPlotItem([self.EBP[i][0]], 
                                                    [self.EBP[i][1]], 
                                                    size=10,
                                                    pen=pg.mkPen(None), 
                                                    brush=mybrush)            

            self.vb.addItem(self.EBPscatter[i])
        
        self.set_EBPButton.setChecked(False)
        
    def toggle_EBP(self):
        
        if self.EBPshown:
        
            for i in range(len(self.EBPscatter)):
                
                if self.EBPscatter[i] is not None:
                    self.vb.removeItem(self.EBPscatter[i])
                else:
                    pass
            
            self.EBPshown = False
            
        else:
            
            for i in range(len(self.EBPscatter)):
                
                if self.EBPscatter[i] is not None:
                    self.vb.addItem(self.EBPscatter[i])
                else:
                    pass
            
            self.EBPshown = True
    
        self.showEBPButton.setChecked(False)
        
    def setup_gui(self):
                
        # widget where the liveview image will be displayed

        imageWidget = pg.GraphicsLayoutWidget()
        self.vb = imageWidget.addViewBox(row=0, col=0)
        self.lplotWidget = linePlotWidget()
        
        # Viewbox and image item where the liveview will be displayed

        self.vb.setMouseMode(pg.ViewBox.RectMode)
        self.img = pg.ImageItem()
        self.img.translate(-0.5, -0.5)
        self.vb.addItem(self.img)
        self.vb.setAspectLocked(True)
        imageWidget.setAspectLocked(True)

        # set up histogram for the liveview image

        self.hist = pg.HistogramLUTItem(image=self.img)
        lut = viewbox_tools.generatePgColormap(cmaps.parula)
        self.hist.gradient.setColorMap(lut)
        self.hist.vb.setLimits(yMin=0, yMax=10000)

        for tick in self.hist.gradient.ticks:
            tick.hide()
        imageWidget.addItem(self.hist, row=0, col=1)
        
        # widget with scanning parameters

        self.paramWidget = QtGui.QFrame()
        self.paramWidget.setFrameStyle(QtGui.QFrame.Panel |
                                       QtGui.QFrame.Raised)
        
        scanParamTitle = QtGui.QLabel('<h2><strong>Scan settings</strong></h2>')
        scanParamTitle.setTextFormat(QtCore.Qt.RichText)

        # LiveView Button

        self.liveviewButton = QtGui.QPushButton('confocal liveview')
        self.liveviewButton.setFont(QtGui.QFont('Helvetica', weight=QtGui.QFont.Bold))
        self.liveviewButton.setCheckable(True)
        self.liveviewButton.setStyleSheet("font-size: 12px; background-color:rgb(180, 180, 180)")
        self.liveviewButton.clicked.connect(self.toggle_liveview)
        
        # ROI buttons

        self.ROIButton = QtGui.QPushButton('ROI')
        self.ROIButton.setCheckable(True)
        self.ROIButton.clicked.connect(self.toggle_ROI)

        self.select_ROIButton = QtGui.QPushButton('select ROI')
        self.select_ROIButton.clicked.connect(self.select_ROI)

#        # Acquire frame button (start)
#
#        self.acquireFrameButton = QtGui.QPushButton('Start acquisition')
#        self.acquireFrameButton.setCheckable(True)
#        self.acquireFrameButton.clicked.connect(self.toggle_frame_acq)
#        
#        # Acquire frame button (stop)
#
#        self.stopAcquireFrameButton = QtGui.QPushButton('Stop acquisition')
#        self.stopAcquireFrameButton.setCheckable(True)
##        self.stopAcquireFrameButton.clicked.connect(self.toggle_frame_acq)   
        
        # Shutter button
        
        self.shutterButton = QtGui.QPushButton('Shutter open/close')
        self.shutterButton.setCheckable(True)
        
        # Flipper button
        
        self.flipperButton = QtGui.QPushButton('Flipper 100x up/down')
        self.flipperButton.setCheckable(True)
        
        # Save current frame button

        self.currentFrameButton = QtGui.QPushButton('Save current frame')

        # preview scan button

        self.preview_scanButton = QtGui.QPushButton('Scan preview')
        self.preview_scanButton.setCheckable(True)
        self.preview_scanButton.clicked.connect(self.preview_scan)
        
        # move to center button
        
        self.moveToROIcenterButton = QtGui.QPushButton('Move to ROI center') 
        self.moveToROIcenterButton.clicked.connect(self.select_ROI)

        
        # line profile button
        
        self.lineProfButton = QtGui.QPushButton('Line profile')
        self.lineProfButton.setCheckable(True)
        self.lineProfButton.clicked.connect(self.line_profile)

        # Scanning parameters

        self.initialPosLabel = QtGui.QLabel('Initial Pos'
                                            ' [x0, y0, z0] (µm)')
        self.initialPosEdit = QtGui.QLineEdit('3 3 10')
        self.scanRangeLabel = QtGui.QLabel('Scan range (µm)')
        self.scanRangeEdit = QtGui.QLineEdit('8')
        self.pxTimeLabel = QtGui.QLabel('Pixel time (µs)')
        self.pxTimeEdit = QtGui.QLineEdit('500')
        self.NofPixelsLabel = QtGui.QLabel('Number of pixels')
        self.NofPixelsEdit = QtGui.QLineEdit('80')
        
        self.pxSizeLabel = QtGui.QLabel('Pixel size (nm)')
        self.pxSizeValue = QtGui.QLineEdit('')
        self.pxSizeValue.setReadOnly(True)
        self.frameTimeLabel = QtGui.QLabel('Frame time (s)')
        self.frameTimeValue = QtGui.QLineEdit('')
        self.frameTimeValue.setReadOnly(True)
        self.maxCountsLabel = QtGui.QLabel('Max counts per pixel')
        self.maxCountsValue = QtGui.QLineEdit('')
        self.frameTimeValue.setReadOnly(True)
        
        self.advancedButton = QtGui.QPushButton('Advanced options')
        self.advancedButton.setCheckable(True)
        self.advancedButton.clicked.connect(self.toggle_advanced)
        

        
        self.auxAccelerationLabel = QtGui.QLabel('Aux acc'
                                                 ' (% of a_max)')
        self.auxAccEdit = QtGui.QLineEdit('1 1 1 1')
        self.waitingTimeLabel = QtGui.QLabel('Scan waiting time (µs)')
        self.waitingTimeEdit = QtGui.QLineEdit('0')
        
        self.toggle_advanced()

        # filename

        self.filenameLabel = QtGui.QLabel('File name')
        self.filenameEdit = QtGui.QLineEdit('filename')

        # folder
        
        today = str(date.today()).replace('-', '')
        root = r'C:\\Data\\'
        folder = root + today
        
        try:  
            os.mkdir(folder)
        except OSError:  
            print(datetime.now(), '[scan] Directory {} already exists'.format(folder))
        else:  
            print(datetime.now(), '[scan] Successfully created the directory {}'.format(folder))
        
        self.folderLabel = QtGui.QLabel('Folder')
        self.folderEdit = QtGui.QLineEdit(folder)
        self.browseFolderButton = QtGui.QPushButton('Browse')
        self.browseFolderButton.setCheckable(True)
        self.browseFolderButton.clicked.connect(self.load_folder)

        # scan selection

        self.scanModeLabel = QtGui.QLabel('Scan type')

        self.scanMode = QtGui.QComboBox()
        self.scanModes = ['xy', 'xz', 'yz']
        self.scanMode.addItems(self.scanModes)
        
        self.detectorType = QtGui.QComboBox()
        self.dettypes = ['APD','photodiode']
        self.detectorType.addItems(self.dettypes)
        
        # widget with EBP parameters and buttons
        
        self.EBPWidget = QtGui.QFrame()
        self.EBPWidget.setFrameStyle(QtGui.QFrame.Panel |
                                       QtGui.QFrame.Raised)
        
        EBPparamTitle = QtGui.QLabel('<h2><strong>Excitation Beam Pattern</strong></h2>')
        EBPparamTitle.setTextFormat(QtCore.Qt.RichText)
        
        self.EBProiButton = QtGui.QPushButton('EBP ROI')
        self.EBProiButton.setCheckable(True)
        self.EBProiButton.clicked.connect(self.toggle_ROI)
        
        self.showEBPButton = QtGui.QPushButton('show/hide EBP')
        self.showEBPButton.setCheckable(True)
        self.showEBPButton.clicked.connect(self.toggle_EBP)

        self.set_EBPButton = QtGui.QPushButton('set EBP')
        self.set_EBPButton.clicked.connect(self.set_EBP)
        
        # EBP selection

        self.EBPtypeLabel = QtGui.QLabel('EBP type')

        self.EBPtype = QtGui.QComboBox()
        self.EBPoptions = ['triangle', 'square']
        self.EBPtype.addItems(self.EBPoptions)
        
        self.Llabel = QtGui.QLabel('L (nm)')
        self.LEdit = QtGui.QLineEdit('100')
        
        # piezo navigation widget
        
        self.positioner = QtGui.QFrame()
        self.positioner.setFrameStyle(QtGui.QFrame.Panel |
                                      QtGui.QFrame.Raised)
        
        self.xUpButton = QtGui.QPushButton("(+x) ►")  # →
        self.xDownButton = QtGui.QPushButton("◄ (-x)")  # ←

        self.yUpButton = QtGui.QPushButton("(+y) ▲")  # ↑
        self.yDownButton = QtGui.QPushButton("(-y) ▼")  # ↓

        
        self.zUpButton = QtGui.QPushButton("(+z) ▲")  # ↑
        self.zDownButton = QtGui.QPushButton("(-z) ▼")  # ↓
        
        self.xStepLabel = QtGui.QLabel('x step (µm)')
        self.xStepEdit = QtGui.QLineEdit('0.050')
        
        self.yStepLabel = QtGui.QLabel('y step (µm)')
        self.yStepEdit = QtGui.QLineEdit('0.050')
        
        self.zStepLabel = QtGui.QLabel('z step (µm)')
        self.zStepEdit = QtGui.QLineEdit('0.050')
        
        # move to button

        self.moveToButton = QtGui.QPushButton('Move to')
        self.moveToLabel = QtGui.QLabel('Move to [x0, y0, z0] (µm)')
        self.moveToEdit = QtGui.QLineEdit('0 0 10')
        
        # scan GUI layout

        grid = QtGui.QGridLayout()
        self.setLayout(grid)

        dockArea = DockArea() 
        grid.addWidget(dockArea, 0, 0)
        
        EBPDock = Dock('EBP')
        EBPDock.setOrientation(o="vertical", force=True)
        EBPDock.updateStyle()
        EBPDock.addWidget(self.EBPWidget)
        dockArea.addDock(EBPDock)
        
        positionerDock = Dock('Positioner')
        positionerDock.setOrientation(o="vertical", force=True)
        positionerDock.updateStyle()
        positionerDock.addWidget(self.positioner)
        dockArea.addDock(positionerDock, 'above', EBPDock)
        
        paramDock = Dock('Scan parameters')
        paramDock.setOrientation(o="vertical", force=True)
        paramDock.updateStyle()
        paramDock.addWidget(self.paramWidget)
        dockArea.addDock(paramDock, 'above', positionerDock)
        
        imageDock = Dock('Confocal view')
        imageDock.addWidget(imageWidget)
        dockArea.addDock(imageDock, 'right', paramDock)

        # paramwidget layout

        subgrid = QtGui.QGridLayout()
        self.paramWidget.setLayout(subgrid)
        
        subgrid.addWidget(scanParamTitle, 0, 0, 1, 3)
        
        subgrid.addWidget(self.scanModeLabel, 2, 2)
        subgrid.addWidget(self.scanMode, 3, 2)
        subgrid.addWidget(self.detectorType, 4, 2)
        subgrid.addWidget(self.liveviewButton, 5, 2)
        
        subgrid.addWidget(self.shutterButton, 7, 2)
        subgrid.addWidget(self.flipperButton, 8, 2)
        subgrid.addWidget(self.currentFrameButton, 9, 2)
        subgrid.addWidget(self.ROIButton, 10, 2)
        subgrid.addWidget(self.select_ROIButton, 11, 2)
        
#        subgrid.addWidget(self.acquireFrameButton, 11, 1)
#        subgrid.addWidget(self.stopAcquireFrameButton, 12, 1)
        
        subgrid.addWidget(self.moveToROIcenterButton, 13, 2)
        subgrid.addWidget(self.lineProfButton, 14, 2)

        subgrid.addWidget(self.initialPosLabel, 2, 0, 1, 2)
        subgrid.addWidget(self.initialPosEdit, 3, 0, 1, 2)
        subgrid.addWidget(self.scanRangeLabel, 4, 0)
        subgrid.addWidget(self.scanRangeEdit, 4, 1)
        subgrid.addWidget(self.pxTimeLabel, 5, 0)
        subgrid.addWidget(self.pxTimeEdit, 5, 1)
        subgrid.addWidget(self.NofPixelsLabel, 6, 0)
        subgrid.addWidget(self.NofPixelsEdit, 6, 1)
        
        subgrid.addWidget(self.pxSizeLabel, 7, 0)
        subgrid.addWidget(self.pxSizeValue, 7, 1)
        subgrid.addWidget(self.frameTimeLabel, 8, 0)
        subgrid.addWidget(self.frameTimeValue, 8, 1)
        subgrid.addWidget(self.maxCountsLabel, 9, 0)
        subgrid.addWidget(self.maxCountsValue, 9, 1)
        
#        subgrid.addWidget(self.emitParamButton, 13, 0)
        
        subgrid.addWidget(self.advancedButton, 11, 0)
        
        subgrid.addWidget(self.auxAccelerationLabel, 15, 0)
        subgrid.addWidget(self.auxAccEdit, 16, 0)
        subgrid.addWidget(self.waitingTimeLabel, 17, 0)
        subgrid.addWidget(self.waitingTimeEdit, 18, 0)
        subgrid.addWidget(self.preview_scanButton, 19, 0)
        
        subgrid.addWidget(self.filenameLabel, 2, 3)
        subgrid.addWidget(self.filenameEdit, 3, 3)
        subgrid.addWidget(self.folderLabel, 4, 3)
        subgrid.addWidget(self.folderEdit, 5, 3)
        subgrid.addWidget(self.browseFolderButton, 6, 3)
    
        self.paramWidget.setFixedHeight(350)
        self.paramWidget.setFixedWidth(400)
        
#        subgrid.setColumnMinimumWidth(1, 130)
#        subgrid.setColumnMinimumWidth(1, 50)
        
        imageWidget.setFixedHeight(500)
        imageWidget.setFixedWidth(500)
        
        # EBP widget layout
        
        subgridEBP = QtGui.QGridLayout()
        self.EBPWidget.setLayout(subgridEBP)
        
        subgridEBP.addWidget(EBPparamTitle, 0, 0, 2, 4)
        
        subgridEBP.addWidget(self.EBProiButton, 2, 0, 1, 1)
        subgridEBP.addWidget(self.set_EBPButton, 3, 0, 1, 1)
        subgridEBP.addWidget(self.showEBPButton, 4, 0, 2, 1)
        subgridEBP.addWidget(self.EBPtypeLabel, 2, 1)
        subgridEBP.addWidget(self.EBPtype, 3, 1)
        subgridEBP.addWidget(self.Llabel, 4, 1)
        subgridEBP.addWidget(self.LEdit, 5, 1)
        
        self.EBPWidget.setFixedHeight(150)
        self.EBPWidget.setFixedWidth(250)
        
        # piezo navigation layout

        layout = QtGui.QGridLayout()
        self.positioner.setLayout(layout)
        
        positionerTitle = QtGui.QLabel('<h2><strong>Position</strong></h2>')
        positionerTitle.setTextFormat(QtCore.Qt.RichText)
        
        layout.addWidget(positionerTitle, 0, 0, 2, 3)
        layout.addWidget(self.xUpButton, 2, 4, 2, 1)
        layout.addWidget(self.xDownButton, 2, 2, 2, 1)
        
        layout.addWidget(self.xStepLabel, 0, 6)        
        layout.addWidget(self.xStepEdit, 1, 6)
        
        layout.addWidget(self.yUpButton, 1, 3, 2, 1)
        layout.addWidget(self.yDownButton, 3, 3, 2, 1)
        
        layout.addWidget(self.yStepLabel, 2, 6)        
        layout.addWidget(self.yStepEdit, 3, 6)

        layout.addWidget(self.zUpButton, 1, 5, 2, 1)
        layout.addWidget(self.zDownButton, 3, 5, 2, 1)
        
        layout.addWidget(self.zStepLabel, 4, 6)        
        layout.addWidget(self.zStepEdit, 5, 6)
        
        layout.addWidget(self.moveToLabel, 6, 1, 1, 3)
        layout.addWidget(self.moveToEdit, 7, 1, 1, 2)
        layout.addWidget(self.moveToButton, 8, 1, 1, 2)
        
        self.positioner.setFixedHeight(250)
        self.positioner.setFixedWidth(400)
        
    # make connections between GUI and worker functions
            
    def make_connection(self, backend):
        
        backend.paramSignal.connect(self.get_backend_param)
        backend.imageSignal.connect(self.get_image)
        
    def closeEvent(self, *args, **kwargs):

        # Emit close signal

        self.closeSignal.emit()
        
        
      
class Backend(QtCore.QObject):
    
    paramSignal = pyqtSignal(dict)
    imageSignal = pyqtSignal(np.ndarray)
#    xyDriftSignal = pyqtSignal()
#    zDriftSignal = pyqtSignal()
    
#    frameAcqSignal = pyqtSignal(np.ndarray, int)
    frameIsDone = pyqtSignal(bool)  # the bool is whether feedback is ON (True) or OFF (False)
#    newFrameSignal = pyqtSignal(bool)
    ROIcenterSignal = pyqtSignal(np.ndarray)
    
    def __init__(self, adwin, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        self.adw = adwin
        self.saveScanData = False
        self.feedback_active = False
        
#        # connect internal signal/slot
#        
#        self.newFrameSignal.connect(self.frame_acquisition)
        
        # edited_scan: True --> size of the useful part of the scan
        # edited_scan: False --> size of the full scan including aux parts
        
        self.edited_scan = True
        
        # 5MHz is max count rate of the P. Elmer APD
        
        self.APDmaxCounts = 5*10**6   

        # Create a timer for the update of the liveview

        self.viewtimer = QtCore.QTimer()

        # Counter for the saved images

        self.imageNumber = 0

        # initialize flag for the linescan function

        self.flag = 0
        
        # initialize fpar_50, fpar_51, fpar_52 ADwin position parameters
        
        pos_zero = tools.convert(0, 'XtoU')
        
        self.adw.Set_FPar(70, pos_zero)
        self.adw.Set_FPar(71, pos_zero)
        self.adw.Set_FPar(72, pos_zero)
        
        # move to z = 10 µm

        self.moveTo(3, 3, 10)

        # initial directory

        self.initialDir = r'C:\Data'
        
        # initialize image
        
        self.image = None
        
    @pyqtSlot(dict)
    def get_frontend_param(self, params):
        
        # updates parameters according to what is input in the GUI
        
        self.detector = params['detectorType']
        self.scantype = params['scanType']
        self.scanRange = params['scanRange']
        self.NofPixels = int(params['NofPixels'])
        self.pxTime = params['pxTime']
        self.initialPos = params['initialPos']
        
        self.waitingTime = params['waitingTime']
        self.a_aux_coeff = params['a_aux_coeff']
        
        self.filename = params['fileName']
        
        self.moveToPos = params['moveToPos']
        
        self.xStep = params['xStep']
        self.yStep = params['yStep']
        self.zStep = params['zStep']
                
        self.calculate_derived_param()
        
    def calculate_derived_param(self):
        
        self.image_to_save = self.image

        self.pxSize = self.scanRange/self.NofPixels   # in µm
        self.frameTime = self.NofPixels**2 * self.pxTime / 10**6
        self.maxCounts = int(self.APDmaxCounts/(1/(self.pxTime*10**-6)))
        self.linetime = (1/1000)*self.pxTime*self.NofPixels  # in ms
        
        #  aux scan parameters

        self.a_max = 4 * 10**-6  # in µm/µs^2

        if np.all(self.a_aux_coeff) <= 1:
            self.a_aux = self.a_aux_coeff * self.a_max
        else:
            self.a_aux[self.a_aux > 1] = self.a_max

        self.NofAuxPixels = 100

        self.waiting_pixels = int(self.waitingTime/self.pxTime)
        self.tot_pixels = (2 * self.NofPixels + 4 * self.NofAuxPixels +
                           self.waiting_pixels)

        # create scan signal

        self.dy = self.pxSize
        self.dz = self.pxSize

        (self.data_t, self.data_x,
         self.data_y) = tools.ScanSignal(self.scanRange,
                                         self.NofPixels,
                                         self.NofAuxPixels,
                                         self.pxTime,
                                         self.a_aux,
                                         self.dy,
                                         self.initialPos[0],
                                         self.initialPos[1],
                                         self.initialPos[2],
                                         self.scantype,
                                         self.waitingTime)

#        self.viewtimer_time = (1/1000) * self.data_t[-1]    # in ms
        
        # TO DO: entender bien esto del timer = 0, leer documentación
        
        self.viewtimer_time = 0  # start timer as soon as possible

        # Create blank image
        # edited_scan = True --> size of the useful part of the scan
        # edited_scan = False --> size of the full scan including aux parts

        if self.edited_scan is True:

#            size = (2 * self.NofPixels, self.NofPixels)
            size = (self.NofPixels, self.NofPixels)

        else:

            size = (self.tot_pixels, self.NofPixels)

        self.blankImage = np.zeros(size)
        self.image = self.blankImage
        self.i = 0

        # load the new parameters into the ADwin system
        
        self.update_device_param()

        # emit calculated parameters

        self.emit_param()
        
    def emit_param(self):
        
        params = dict()
        
        params['frameTime'] = self.frameTime
        params['pxSize'] = self.pxSize
        params['maxCounts'] = self.maxCounts
        params['initialPos'] = np.float64(self.initialPos)
        
        self.paramSignal.emit(params)
        
    def update_device_param(self):
        
        if self.detector == 'APD':
            self.adw.Set_Par(3, 0)  # Digital input (APD)

        if self.detector == 'photodiode':
            self.adw.Set_Par(3, 1)  # Analog input (photodiode)

        # select scan type

        if self.scantype == 'xy':

            self.adw.Set_FPar(10, 1)
            self.adw.Set_FPar(11, 2)

        if self.scantype == 'xz':

            self.adw.Set_FPar(10, 1)
            self.adw.Set_FPar(11, 6)

        if self.scantype == 'yz':

            self.adw.Set_FPar(10, 2)
            self.adw.Set_FPar(11, 6)

        #  initial positions x and y
        
        self.x_i = self.initialPos[0]
        self.y_i = self.initialPos[1]
        self.z_i = self.initialPos[2]

        self.x_offset = 0
        self.y_offset = 0
        self.z_offset = 0

        #  load ADwin parameters

        self.adw.Set_Par(1, self.tot_pixels)

        self.data_t_adwin = tools.timeToADwin(self.data_t)
        self.data_x_adwin = tools.convert(self.data_x, 'XtoU')
        self.data_y_adwin = tools.convert(self.data_y, 'XtoU')

        # repeat last element because time array has to have one more
        # element than position array

        dt = self.data_t_adwin[-1] - self.data_t_adwin[-2]

        self.data_t_adwin = np.append(self.data_t_adwin,
                                      (self.data_t_adwin[-1] + dt))

        # prepare arrays for conversion into ADwin-readable data

        self.time_range = np.size(self.data_t_adwin)
        self.space_range = np.size(self.data_x_adwin)

        self.data_t_adwin = np.array(self.data_t_adwin, dtype='int')
        self.data_x_adwin = np.array(self.data_x_adwin, dtype='int')
        self.data_y_adwin = np.array(self.data_y_adwin, dtype='int')

        self.data_t_adwin = list(self.data_t_adwin)
        self.data_x_adwin = list(self.data_x_adwin)
        self.data_y_adwin = list(self.data_y_adwin)

        self.adw.SetData_Long(self.data_t_adwin, 2, 1, self.time_range)
        self.adw.SetData_Long(self.data_x_adwin, 3, 1, self.space_range)
        self.adw.SetData_Long(self.data_y_adwin, 4, 1, self.space_range)

    def set_moveTo_param(self, x_f, y_f, z_f, n_pixels_x=128, n_pixels_y=128,
                         n_pixels_z=128, pixeltime=2000):

        x_f = tools.convert(x_f, 'XtoU')
        y_f = tools.convert(y_f, 'XtoU')
        z_f = tools.convert(z_f, 'XtoU')

#        print(x_f, y_f, z_f)

        self.adw.Set_Par(21, n_pixels_x)
        self.adw.Set_Par(22, n_pixels_y)
        self.adw.Set_Par(23, n_pixels_z)

        self.adw.Set_FPar(23, x_f)
        self.adw.Set_FPar(24, y_f)
        self.adw.Set_FPar(25, z_f)

        self.adw.Set_FPar(26, tools.timeToADwin(pixeltime))

    def moveTo(self, x_f, y_f, z_f):

        self.set_moveTo_param(x_f, y_f, z_f)
        self.adw.Start_Process(2)

    def moveTo_action(self):

        self.moveTo(*self.moveToPos)
        
    def moveTo_roi_center(self):
        
        self.ROIcenter = self.initialPos + np.array([self.scanRange/2, self.scanRange/2, 0])
        
        print('[scan] self.initialPos[0:2]', self.initialPos[0:2])
        print('[scan] center', self.ROIcenter)
        
        self.moveTo(*self.ROIcenter)
        self.ROIcenterSignal.emit(self.ROIcenter)
        
    def relative_move(self, axis, direction):
        
        if axis == 'x' and direction == 'up':
            
            newPos_µm = self.initialPos[0] - self.xStep
            newPos_µm = round(newPos_µm, 3)
            self.initialPos = np.array([newPos_µm, self.initialPos[1],
                                        self.initialPos[2]])
            
        if axis == 'x' and direction == 'down':
            
            newPos_µm = self.initialPos[0] + self.xStep
            newPos_µm = np.around(newPos_µm, 3)
            self.initialPos = np.array([newPos_µm, self.initialPos[1],
                                        self.initialPos[2]])
            
        if axis == 'y' and direction == 'up':
            
            newPos_µm = self.initialPos[1] + self.yStep
            newPos_µm = np.around(newPos_µm, 3)       
            self.initialPos = np.array([self.initialPos[0], newPos_µm,
                                        self.initialPos[2]])
            
        if axis == 'y' and direction == 'down':
            
            newPos_µm = self.initialPos[1] - self.yStep
            newPos_µm = np.around(newPos_µm, 3)
            self.initialPos = np.array([self.initialPos[0], newPos_µm,
                                        self.initialPos[2]])
            
        if axis == 'z' and direction == 'up':
            
            newPos_µm = self.initialPos[2] + self.zStep
            newPos_µm = np.around(newPos_µm, 3)
            self.initialPos = np.array([self.initialPos[0], self.initialPos[1], 
                                        newPos_µm])
        
        if axis == 'z' and direction == 'down':
            
            newPos_µm = self.initialPos[2] - self.zStep
            newPos_µm = np.around(newPos_µm, 3)
            self.initialPos = np.array([self.initialPos[0], self.initialPos[1], 
                                        newPos_µm])
    
        self.update_device_param()
        self.emit_param()    
        
#    @pyqtSlot()
#    def toggle_feedback(self):
#        
#        if self.feedback_active is False:
#            self.feedback_active = True
#            print('confocal feedback loop ON')
#            
#        else:
#            
#            self.feedback_active = False
#            print('confocal feedback loop OFF')
    
    @pyqtSlot()
    def toggle_acquire_frames(self):
        
        if self.acquire_frames is False:
            self.acquire_frames = True
            print('Start acquiring frames')
            
        else:
            
            self.acquire_frames = False
            print('Stop acquiring frames')
        
    def z_drift_correction(self):
        
        self.zDriftSignal.emit()
        
#    @pyqtSlot(float, float, float)
#    def get_drift_corrected_param(self, x, y, z):
#        
#        print('got drift corrected parameters', x, y, z)
#        self.initialPos = np.array([x, y, z])
#        self.update_device_param()
#        
#        if self.frame_acquisition_ON: # TO DO: change by taking into account number of frames wished or GUI signal
#            
#            self.newFrameSignal.emit(True)
        
    def plot_scan_signal(self):
        
        # save scan plot (x vs t)
        plt.figure()
        plt.title('Scan plot x vs t')
        plt.plot(self.data_t_adwin[0:-1], self.data_x_adwin, 'go')
        plt.xlabel('t (ADwin time)')
        plt.ylabel('V (DAC units)')

        fname = tools.getUniqueName(self.filename)
        fname = fname + '_scan_plot'
        plt.savefig(fname, dpi=None, facecolor='w', edgecolor='w',
                    orientation='portrait', papertype=None, format=None,
                    transparent=False, bbox_inches=None, pad_inches=0.1,
                    frameon=None)
            
#    @pyqtSlot(bool)
#    def frame_acquisition(self, fabool):
#        
#        if fabool:
#            
#            self.liveview_stop()
#            self.frame_acquisition_start()
#            
#        else:
#            
#            self.frame_acquisition_stop()
#        
#    def frame_acquisition_start(self):
#
#        self.acquisitionMode = 'frame'
#
#        # save scan plot (x vs t)
#
#        if self.saveScanData:
#
#            plt.figure('Scan plot x vs t')
#            plt.plot(self.data_t_adwin[0:-1], self.data_x_adwin, 'go')
#            plt.xlabel('t (ADwin time)')
#            plt.ylabel('V (DAC units)')
#    
#            fname = tools.getUniqueName(self.filename)
#            fname = fname + '_scan_plot'
#            plt.savefig(fname, dpi=None, facecolor='w', edgecolor='w',
#                        orientation='portrait', papertype=None, format=None,
#                        transparent=False, bbox_inches=None, pad_inches=0.1,
#                        frameon=None)
#        
#        # restar the slow axis
#        
#        self.y_offset = 0
#
#        # move to initial position smoothly
#
#        if self.scantype == 'xy':
#
#            self.moveTo(self.x_i, self.y_i, self.z_i)
#
#        if self.scantype == 'xz':
#
#            self.moveTo(self.x_i, self.y_i + self.scanRange/2,
#                        self.z_i - self.scanRange/2)
#
#        if self.scantype == 'yz':
#
#            self.moveTo(self.x_i + self.scanRange/2, self.y_i,
#                        self.z_i - self.scanRange/2)
#
#        self.i = 0
#
#        # start updateView timer
#
#        self.viewtimer.start(self.viewtimer_time)
#
#    def frame_acquisition_stop(self):
#
#        self.viewtimer.stop()
#
#        # experiment parameters
#
#        name = tools.getUniqueName(self.filename)
#        now = time.strftime("%c")
#        tools.saveConfig(self, now, name)
#
#        # save image
#
#        data = self.image
#
#        result = Image.fromarray(data.astype('uint16'))
#        result.save(r'{}.tiff'.format(name))
#        
#        print(name)
#
#        self.imageNumber += 1
#        
#        self.emit_param()
#        self.frameIsDone.emit(self.feedback_active)   
#        
#        print('frame is done')
        
#        self.gui.acquireFrameButton.setChecked(False)
        
#        self.frameAcqSignal.emit(data, self.imageNumber)
        
#    def stop_continous_acq(self):
#        
#        self.frame_acquisition_stop()
#        self.frame_acquisition_ON = False
#        
#    def start_continous_acq(self):
#        
#        self.frame_acquisition_ON = True
        
        
    def save_current_frame(self):
        
        # experiment parameters
        
        name = tools.getUniqueName(self.filename)
        now = time.strftime("%c")
        tools.saveConfig(self, now, name)

        # save image
        
        data = self.image_to_save
        result = Image.fromarray(data.astype('uint16'))
        result.save(r'{}.tiff'.format(name))
        
        print('[scan] Saved current frame', name)

#        self.gui.currentFrameButton.setChecked(False)
        
    def line_acquisition(self):

        # TO DO: fix problem of waiting time

        self.adw.Start_Process(1)

#        # flag changes when process is finished

        if (((1/1000) * self.data_t[-1]) < 240):   # in ms 

            while self.flag == 0:
                self.flag = self.adw.Get_Par(2)
        
        else: # only for lines longer than 240 ms
            
            print('[scan] Linetime longer than 240 ms')
            
            line_time = (1/1000) * self.data_t[-1]  # in ms
            wait_time = line_time * 1.05
            time.sleep(wait_time/1000)

        line_data = self.adw.GetData_Long(1, 0, self.tot_pixels)
        line_data[0] = 0  # TO DO: fix the high count error on first element

        return line_data

    @pyqtSlot(bool)
    def liveview(self, lvbool):
        
        if lvbool:
            
            self.acquisitionMode = 'liveview'
            self.liveview_start()
            
        else:
            
            self.liveview_stop()

    def liveview_start(self):
        
#        self.plot_scan_signal()

        if self.scantype == 'xy':

            self.moveTo(self.x_i, self.y_i, self.z_i)

        if self.scantype == 'xz':

            self.moveTo(self.x_i, self.y_i + self.scanRange/2,
                        self.z_i - self.scanRange/2)

        if self.scantype == 'yz':

            self.moveTo(self.x_i + self.scanRange/2, self.y_i,
                        self.z_i - self.scanRange/2)

        self.viewtimer.start(self.viewtimer_time)

    def liveview_stop(self):

        self.viewtimer.stop()

    def update_view(self):
        
        if self.scantype == 'xy':

            dy = tools.convert(self.dy, 'ΔXtoU')
            self.y_offset = int(self.y_offset + dy)
            self.adw.Set_FPar(2, self.y_offset)

        if self.scantype == 'xz' or self.scantype == 'yz':

            dz = tools.convert(self.dz, 'ΔXtoU')
            self.z_offset = int(self.z_offset + dz)
            self.adw.Set_FPar(2, self.z_offset)

        self.lineData = self.line_acquisition()

        if self.edited_scan is True:

            c0 = self.NofAuxPixels
            c1 = self.NofAuxPixels + self.NofPixels

            self.lineData_edited = self.lineData[c0:c1]
            self.image[:, self.NofPixels-1-self.i] = self.lineData_edited

        else:

            self.image[:, self.NofPixels-1-self.i] = self.lineData
          
#            # display image after every scanned line
            
        self.image_to_save = self.image
        self.imageSignal.emit(self.image)

        if self.i < self.NofPixels-1:

            self.i = self.i + 1

        else:

            print(datetime.now(), '[scan] Frame ended')

            self.i = 0
            self.y_offset = 0
            self.z_offset = 0

            if self.scantype == 'xy':

                self.moveTo(self.x_i, self.y_i, self.z_i)
                    
            if self.scantype == 'xz':

                self.moveTo(self.x_i, self.y_i + self.scanRange/2,
                            self.z_i - self.scanRange/2)

            if self.scantype == 'yz':

                self.moveTo(self.x_i + self.scanRange/2, self.y_i,
                            self.z_i - self.scanRange/2)
                
            if self.acquisitionMode == 'frame':
                
                self.liveview_stop()
                self.frameIsDone.emit()
                
            self.update_device_param()  
            
    @pyqtSlot(bool)
    def toggle_shutter(self, val):
        
        if val is True:
            
            self.shutter_state = True
            
            self.adw.Set_Par(55, 0)
            self.adw.Set_Par(50, 1)
            self.adw.Start_Process(5)
            
            print('[scan] Shutter opened')
            
        if val is False:
            
            self.shutte_state = False
            
            self.adw.Set_Par(55, 0)
            self.adw.Set_Par(50, 0)
            self.adw.Start_Process(5)

            print('[scan] Shutter closed')
            
    @pyqtSlot(bool)
    def toggle_flipper(self, val):
        
        if val is True:
            
            self.flipper_state = True
            
            self.adw.Set_Par(55, 1)
            self.adw.Set_Par(51, 1)
            self.adw.Start_Process(5)
            
            print('[scan] Flipper up')
            
        if val is False:
            
            self.flipper_state = False
            
            self.adw.Set_Par(55, 1)
            self.adw.Set_Par(51, 0)
            self.adw.Start_Process(5)

            print('[scan] Flipper down')
            
#    @pyqtSlot()
#    def get_ROI_center_request(self):
#        
#        print(datetime.now(), '[scan] got ROI request')
        
    def emit_ROI_center(self):
        
        self.ROIcenterSignal.emit(self.ROIcenter)
        
        print('[scan] ROI center emitted')

                      
    def make_connection(self, frontend):
        
#        frontend.liveviewButton.clicked.connect(self.liveview)
        frontend.liveviewSignal.connect(self.liveview)
#        frontend.frameacqSignal.connect(self.frame_acquisition)
#        frontend.frameacqSignal.connect(self.start_continous_acq)
#        frontend.stopAcquireFrameButton.clicked.connect(self.stop_continous_acq)
#        frontend.acquireFrameButton.clicked.connect(self.frame_acquisition)
        frontend.moveToROIcenterButton.clicked.connect(self.moveTo_roi_center)
        frontend.currentFrameButton.clicked.connect(self.save_current_frame)
        frontend.moveToButton.clicked.connect(self.moveTo_action)
        frontend.paramSignal.connect(self.get_frontend_param)
        frontend.closeSignal.connect(self.stop)
#        frontend.feedbackLoopBox.stateChanged.connect(self.toggle_feedback)
        frontend.shutterButton.clicked.connect(lambda: self.toggle_shutter(frontend.shutterButton.isChecked()))
        frontend.flipperButton.clicked.connect(lambda: self.toggle_flipper(frontend.flipperButton.isChecked()))
        
        frontend.xUpButton.pressed.connect(lambda: self.relative_move('x', 'up'))
        frontend.xDownButton.pressed.connect(lambda: self.relative_move('x', 'down'))
        frontend.yUpButton.pressed.connect(lambda: self.relative_move('y', 'up'))
        frontend.yDownButton.pressed.connect(lambda: self.relative_move('y', 'down'))        
        frontend.zUpButton.pressed.connect(lambda: self.relative_move('z', 'up'))
        frontend.zDownButton.pressed.connect(lambda: self.relative_move('z', 'down'))
          
    def stop(self):

        self.liveview_stop()
        
        # Go back to 0 position

        x_0 = 0
        y_0 = 0
        z_0 = 0

        self.moveTo(x_0, y_0, z_0)
        

if __name__ == '__main__':

    app = QtGui.QApplication([])
    app.setStyle(QtGui.QStyleFactory.create('fusion'))
#    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    
    DEVICENUMBER = 0x1
    adw = ADwin.ADwin(DEVICENUMBER, 1)
    setupDevice(adw)
    
    worker = Backend(adw)    
    gui = Frontend()
    
    worker.make_connection(gui)
    gui.make_connection(worker)
    
    gui.emit_param()
    worker.emit_param()
    
#
    scanThread = QtCore.QThread()
    worker.moveToThread(scanThread)
    worker.viewtimer.moveToThread(scanThread)
    worker.viewtimer.timeout.connect(worker.update_view)
    
    scanThread.start()

    
    gui.setWindowTitle('Confocal scan')
    gui.show()

    app.exec_()
