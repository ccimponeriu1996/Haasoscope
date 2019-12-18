# -*- coding: utf-8 -*-
"""
pyqtgraph widget with UI template created with Qt Designer
"""

import numpy as np
import os, sys, time
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg
from serial import SerialException

import HaasoscopeLibQt
reload(HaasoscopeLibQt) # in case you changed it, and to always load some defaults

#Some pre-options
#HaasoscopeLibQt.num_board = 2 # Number of Haasoscope boards to read out (default is 1)
#HaasoscopeLibQt.ram_width = 12 # width in bits of sample ram to use (e.g. 9==512 samples (default), 12(max)==4096 samples) (min is 2)
#HaasoscopeLibQt.max10adcchans =  [(0,110),(0,118)] #[(0,110),(0,118),(1,110),(1,118)] #max10adc channels to draw (board, channel on board), channels: 110=ain1, 111=pin6, ..., 118=pin14, 119=temp # default is none, []

d = HaasoscopeLibQt.Haasoscope()
d.construct()

#Some other options
#d.serport="COM7" # the name of the serial port on your computer, connected to Haasoscope, like /dev/ttyUSB0 or COM8, leave blank to detect automatically!
#d.serialdelaytimerwait=0 #50 #100 #150 #300 # 600 # delay (in 2 us steps) between each 32 bytes of serial output (set to 600 for some slow USB serial setups, but 0 normally)
#d.dolockin=True # whether to calculate the lockin info on the FPGA and read it out (off by default)
#d.db=True #turn on debugging

app = QtGui.QApplication.instance()
standalone = app is None
if standalone:
    app = QtGui.QApplication(sys.argv)

# Define main window class from template
WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType("Haasoscope.ui")

class MainWindow(TemplateBaseClass):  
    def __init__(self):
        TemplateBaseClass.__init__(self)
        
        # Create the main window
        self.ui = WindowTemplate()
        self.ui.setupUi(self)
        self.ui.runButton.clicked.connect(self.dostartstop)
        self.ui.actionTest.triggered.connect(self.actionTest)
        self.ui.verticalSlider.valueChanged.connect(self.triggerlevelchanged)
        self.ui.horizontalSlider.valueChanged.connect(self.triggerposchanged)
        self.ui.rollingButton.clicked.connect(self.rolling)
        self.ui.singleButton.clicked.connect(self.single)
        self.ui.timeslowButton.clicked.connect(self.timeslow)
        self.ui.timefastButton.clicked.connect(self.timefast)
        self.ui.risingedgeCheck.stateChanged.connect(self.risingfalling)
        self.ui.exttrigCheck.stateChanged.connect(self.exttrig)
        self.ui.totBox.valueChanged.connect(self.tot)
        self.ui.autorearmCheck.stateChanged.connect(self.autorearm)
        self.ui.avgCheck.stateChanged.connect(self.avg)
        self.ui.logicCheck.stateChanged.connect(self.logic)
        self.ui.highresCheck.stateChanged.connect(self.highres)
        self.ui.usb2Check.stateChanged.connect(self.usb2)
        self.ui.gridCheck.stateChanged.connect(self.grid)
        self.ui.markerCheck.stateChanged.connect(self.marker)
        self.ui.resampBox.valueChanged.connect(self.resamp)
        self.ui.upposButton.clicked.connect(self.uppos)
        self.ui.downposButton.clicked.connect(self.downpos)
        self.ui.chanBox.valueChanged.connect(self.selectchannel)
        self.ui.dacBox.valueChanged.connect(self.setlevel)
        self.ui.minidisplayCheck.stateChanged.connect(self.minidisplay)
        self.ui.acdcCheck.stateChanged.connect(self.acdc)
        self.ui.gainCheck.stateChanged.connect(self.gain)
        self.ui.supergainCheck.stateChanged.connect(self.supergain)
        self.ui.actionRead_from_file.triggered.connect(self.actionRead_from_file)
        self.ui.actionStore_to_file.triggered.connect(self.actionStore_to_file)
        self.ui.actionDo_autocalibration.triggered.connect(self.actionDo_autocalibration)
        
        self.ui.statusBar.showMessage("yes")
        self.ui.textBrowser.setText("stopped")
        
        self.db=True
        self.lastTime = time.time()
        self.fps = None
        self.lines = []
        self.otherlines = []
        
        self.savetofile=False # save scope data to file
        if self.savetofile:
            self.outf = open("Haasoscope_out_"+time.strftime("%Y%m%d-%H%M%S")+".csv","wt")
        
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updateplot)
        
        self.selectchannel()
        self.show()

    def selectchannel(self):
        d.selectedchannel=self.ui.chanBox.value()
        self.ui.textBrowser.setText("going on channel "+str(d.selectedchannel))
        self.ui.dacBox.setValue(d.chanlevel[d.selectedchannel])
        if d.chanforscreen == d.selectedchannel:   self.ui.minidisplayCheck.setCheckState(QtCore.Qt.Checked)
        else:   self.ui.minidisplayCheck.setCheckState(QtCore.Qt.Unchecked)
        if d.acdc[d.selectedchannel]:   self.ui.acdcCheck.setCheckState(QtCore.Qt.Unchecked)
        else:   self.ui.acdcCheck.setCheckState(QtCore.Qt.Checked)
        if d.gain[d.selectedchannel]:   self.ui.gainCheck.setCheckState(QtCore.Qt.Unchecked)
        else:   self.ui.gainCheck.setCheckState(QtCore.Qt.Checked)
        if d.supergain[d.selectedchannel]:   self.ui.supergainCheck.setCheckState(QtCore.Qt.Unchecked)
        else:   self.ui.supergainCheck.setCheckState(QtCore.Qt.Checked)
        if d.havereadswitchdata: self.ui.supergainCheck.setEnabled(False)
        chanonboard = d.selectedchannel%HaasoscopeLibQt.num_chan_per_board
        theboard = HaasoscopeLibQt.num_board-1-d.selectedchannel/HaasoscopeLibQt.num_chan_per_board
        if d.havereadswitchdata:
            if d.testBit(d.switchpos[theboard],chanonboard):   self.ui.ohmCheck.setCheckState(QtCore.Qt.Unchecked)
            else:   self.ui.ohmCheck.setCheckState(QtCore.Qt.Checked)
    
    def acdc(self):
        if self.ui.acdcCheck.checkState() == QtCore.Qt.Checked: #ac coupled
            if d.acdc[d.selectedchannel]:
                d.setacdc()
        if self.ui.acdcCheck.checkState() == QtCore.Qt.Unchecked: #dc coupled
            if not d.acdc[d.selectedchannel]:
                d.setacdc()
    
    def gain(self):
        if self.ui.gainCheck.checkState() == QtCore.Qt.Checked: #x10
            if d.gain[d.selectedchannel]:
                d.tellswitchgain(d.selectedchannel)
        if self.ui.gainCheck.checkState() == QtCore.Qt.Unchecked: #x1
            if not d.gain[d.selectedchannel]:
                d.tellswitchgain(d.selectedchannel)
 
    def supergain(self):
        if self.ui.supergainCheck.checkState() == QtCore.Qt.Checked: #x100
            if d.supergain[d.selectedchannel]:
                d.togglesupergainchan(d.selectedchannel)
        if self.ui.supergainCheck.checkState() == QtCore.Qt.Unchecked: #x1
            if not d.supergain[d.selectedchannel]:
                d.togglesupergainchan(d.selectedchannel)
                   
    def minidisplay(self):
        if self.ui.minidisplayCheck.checkState()==QtCore.Qt.Checked:
            if d.chanforscreen != d.selectedchannel:
                d.tellminidisplaychan(d.selectedchannel)
    
    def posamount(self):
        amount=10
        modifiers = app.keyboardModifiers()
        if modifiers == QtCore.Qt.ShiftModifier:
            amount*=5
        elif modifiers == QtCore.Qt.ControlModifier:
            amount/=10
        return amount
    def uppos(self):
         d.adjustvertical(True,self.posamount())
         self.ui.dacBox.setValue(d.chanlevel[d.selectedchannel])
    def downpos(self):
         d.adjustvertical(False,self.posamount())
         self.ui.dacBox.setValue(d.chanlevel[d.selectedchannel])
    def setlevel(self):
        if d.chanlevel[d.selectedchannel] != self.ui.dacBox.value():
            d.chanlevel[d.selectedchannel] = self.ui.dacBox.value()
            d.rememberdacvalue()
            d.setdacvalue()
    
    def actionRead_from_file(self):
        d.readcalib()
        
    def actionStore_to_file(self):
        d.storecalib()
        
    def actionDo_autocalibration(self):
        print "starting autocalibration"
        d.autocalibchannel=0
        
    def exttrig(self):
         d.toggleuseexttrig()
         
    def tot(self):
        d.triggertimethresh = self.ui.totBox.value()
        d.settriggertime(d.triggertimethresh)
        
    def autorearm(self):
        d.toggleautorearm()
        
    def avg(self):
        d.average = not d.average
        print "average",d.average
        
    def logic(self):
        d.togglelogicanalyzer()
        if d.dologicanalyzer:
             for l in np.arange(8):
                c=(0,0,0)
                pen = pg.mkPen(color=c) # add linewidth=1.7, alpha=.65
                self.lines[d.logicline1+l].setPen(pen)
        else:
            for l in np.arange(8):
                self.lines[d.logicline1+l].setPen(None)
        
    def highres(self):
        d.togglehighres()
        
    def usb2(self):
        d.toggledousb()
        
    def grid(self):
        if self.ui.gridCheck.isChecked():
            self.ui.plot.showGrid(x=True, y=True)
        else:
            self.ui.plot.showGrid(x=False, y=False)
            
    def marker(self):
         if self.ui.markerCheck.isChecked():
            for l in range(self.nlines):
                self.lines[l].setSymbol("o")
         else:
            for l in range(self.nlines):
                self.lines[l].setSymbol(None)
                
    def resamp(self):
        d.sincresample = self.ui.resampBox.value()
        if d.sincresample>0: d.xydata=np.empty([HaasoscopeLibQt.num_chan_per_board*HaasoscopeLibQt.num_board,2,d.sincresample*(d.num_samples-1)],dtype=float)
        else: d.xydata=np.empty([HaasoscopeLibQt.num_chan_per_board*HaasoscopeLibQt.num_board,2,1*(d.num_samples-1)],dtype=float)
        self.prepareforsamplechange();
    
    def dostartstop(self):        
        if d.paused:
            self.timer.start(0)
            d.paused=False
            self.ui.runButton.setChecked(True)            
        else:
            self.timer.stop()
            d.paused=True
            self.ui.runButton.setChecked(False)
    
    def prepareforsamplechange(self): #called when sampling is changed, to reset some things
        d.recordedchannel=[]
        #if d.doxyplot:
          #  plt.close(self.figxy)
        #if d.recorddata:
          #  plt.close(self.fig2d)
        
    def triggerlevelchanged(self,value):
        d.settriggerthresh(value)
        self.hline = (float(  value-128  )*d.yscale/256 )
        self.otherlines[1].setData( [d.min_x, d.max_x], [self.hline, self.hline] ) # horizontal line showing trigger threshold
    
    def triggerposchanged(self,value):
        if value>253 or value<3: return
        d.settriggerpoint(int(value*d.num_samples/256.))
        self.vline = float(  2*(value-128)/256. *d.xscale /d.xscaling)
        self.otherlines[0].setData( [self.vline, self.vline], [d.min_y, d.max_y] ) # vertical line showing trigger time
    
    def rolling(self):
         d.rolltrigger = not d.rolltrigger
         d.tellrolltrig(d.rolltrigger)
         self.ui.rollingButton.setChecked(d.rolltrigger)
         if d.rolltrigger: self.ui.rollingButton.setText("Rolling/Auto")
         else: self.ui.rollingButton.setText("Normal")
         app.processEvents()
        
    def single(self):
        d.getone = not d.getone
        self.ui.singleButton.setChecked(d.getone)
        
    def timefast(self):
        d.telldownsample(d.downsample-1)
        self.timechanged()
    
    def timeslow(self):
        d.telldownsample(d.downsample+1)
        self.timechanged()
    
    def timechanged(self):
        self.ui.plot.setRange(xRange=(d.min_x, d.max_x), yRange=(d.min_y, d.max_y)) 
        self.ui.plot.setLabel('bottom', d.xlabel)
        
    def risingfalling(self):
        d.fallingedge=not self.ui.risingedgeCheck.checkState()
        d.settriggertype(d.fallingedge)
        
    def actionTest(self):
        print "Handling actionTest"
        self.ui.statusBar.showMessage("no!")
        #self.timer.stop()
        self.updateplot()
    
    def launch(self):        
        self.ui.plot.setBackground('w')
        self.nlines = HaasoscopeLibQt.num_chan_per_board*HaasoscopeLibQt.num_board+len(HaasoscopeLibQt.max10adcchans)
        if self.db: print "nlines=",self.nlines
        for l in np.arange(self.nlines):
            maxchan=l-HaasoscopeLibQt.num_chan_per_board*HaasoscopeLibQt.num_board
            c=(0,0,0)
            if maxchan>=0: # these are the slow ADC channels
                if HaasoscopeLibQt.num_board>1:
                    board = int(HaasoscopeLibQt.num_board-1-HaasoscopeLibQt.max10adcchans[maxchan][0])
                    if board%4==0: c=(1-0.1*maxchan,0,0)
                    if board%4==1: c=(0,1-0.1*maxchan,0)
                    if board%4==2: c=(0,0,1-0.1*maxchan)
                    if board%4==3: c=(1-0.1*maxchan,0,1-0.1*maxchan)
                else:
                    c=(0.1*(maxchan+1),0.1*(maxchan+1),0.1*(maxchan+1))
                pen = pg.mkPen(color=c) # add linewidth=0.5, alpha=.5
                line = self.ui.plot.plot(pen=pen,name="slowadc_"+str(HaasoscopeLibQt.max10adcchans[maxchan]))
            else: # these are the fast ADC channels
                chan=l%4
                if HaasoscopeLibQt.num_board>1:
                    board=l/4
                    if board%4==0: c=(1-0.2*chan,0,0)
                    if board%4==1: c=(0,1-0.2*chan,0)
                    if board%4==2: c=(0,0,1-0.2*chan)
                    if board%4==3: c=(1-0.2*chan,0,1-0.2*chan)
                else:
                    if chan==0: c="r"
                    if chan==1: c="g"
                    if chan==2: c="b"
                    if chan==3: c="m"
                pen = pg.mkPen(color=c) # add linewidth=1.0, alpha=.9
                line = self.ui.plot.plot(pen=pen,name=d.chtext+str(l))
            self.lines.append(line)
        self.ui.chanBox.setMaximum(HaasoscopeLibQt.num_chan_per_board*HaasoscopeLibQt.num_board-1)
        self.ui.slowchanBox.setMaximum(len(HaasoscopeLibQt.max10adcchans)-1)
        #for the logic analyzer
        for l in np.arange(8):
            line = self.ui.plot.plot(pen=None,name="logic_"+str(l)) # not drawn by default
            self.lines.append(line)
            if l==0: d.logicline1=len(self.lines)-1 # remember index where this first logic line is
        #other data to draw
        if d.fitline1>-1:
            pen = pg.mkPen(color="purple") # add linewidth=0.5, alpha=.5
            line = self.ui.plot.plot(pen=None,name="fitline1") # not drawn by default
            self.lines.append(line)
            d.fitline1=len(self.lines)-1 # remember index where this line is
        #other stuff
        d.setxaxis()
        d.setyaxis()
        self.timechanged()
        self.ui.plot.showGrid(x=True, y=True)
        self.vline=0.0
        pen = pg.mkPen(color="k",width=1.0,style=QtCore.Qt.DashLine)
        line = self.ui.plot.plot([self.vline, self.vline], [-2.0, 2.0], pen=pen,name="trigger time vert")
        self.otherlines.append(line)
        self.hline = 0.0
        pen = pg.mkPen(color="k",width=1.0,style=QtCore.Qt.DashLine)
        line = self.ui.plot.plot( [-2.0, 2.0], [self.hline, self.hline], pen=pen,name="trigger thresh horiz")
        self.otherlines.append(line)
        self.hline2 = 0.0
        pen = pg.mkPen(color="b",width=1.0,style=QtCore.Qt.DashLine)
        line = self.ui.plot.plot( [-2.0, 2.0], [self.hline2, self.hline2], pen=None,name="trigger thresh2 horiz") # not drawn by default
        self.otherlines.append(line)
                
    """
    def drawtext(self):
        height = 0.25 # height up from bottom to start drawing text
        xpos = 1.02 # how far over to the right to draw
        if self.firstdrawtext:
            self.texts.append(self.ax.text(xpos, height, self.chantext(),horizontalalignment='left', verticalalignment='top',transform=self.ax.transAxes))
            self.firstdrawtext=False
        else:
            self.texts[0].remove()
            self.texts[0]=(self.ax.text(xpos, height, self.chantext(),horizontalalignment='left', verticalalignment='top',transform=self.ax.transAxes))
            #for txt in self.ax.texts: print txt # debugging
        self.needtoredrawtext=True
        plt.draw()        
        
    def onclick(self,event):
            if event.button==2: #middle click
                if self.keyShift:# if shift is held, turn off threshold2
                    self.settriggerthresh2(0)
                    self.otherlines[2].set_visible(False)
                else:
                    self.hline2 = event.ydata
                    self.settriggerthresh2(int(  self.hline2/(self.yscale/256.) + 128  ))                
                    self.otherlines[2].set_visible(True) # starts off being hidden, so now show it!
                    self.otherlines[2].set_data( [self.min_x, self.max_x], [self.hline2, self.hline2] )
    """        
    
    def closeEvent(self, event):
        print "Handling closeEvent"
        self.timer.stop()
        d.cleanup()
        if self.savetofile: self.outf.close()
        
    def updateplot(self):
        self.mainloop()        
        for l in range(self.nlines):
            maxchan=l-HaasoscopeLibQt.num_chan_per_board*HaasoscopeLibQt.num_board
            if maxchan>=0: # these are the slow ADC channels
                self.lines[l].setData(d.xydataslow[maxchan][0],d.xydataslow[maxchan][1])
            else:
                self.lines[l].setData(d.xydata[l][0],d.xydata[l][1])
        if d.dologicanalyzer:
             for l in np.arange(8):
                 self.lines[d.logicline1+l].setData(d.xydatalogic[l][0],d.xydatalogic[l][1])
        now = time.time()
        dt = now - self.lastTime
        self.lastTime = now
        if self.fps is None:
            self.fps = 1.0/dt
        else:
            s = np.clip(dt*3., 0, 1)
            self.fps = self.fps * (1-s) + (1.0/dt) * s
        self.ui.plot.setTitle('%0.2f fps' % self.fps)
        app.processEvents()
    
    nevents=0; oldnevents=0; tinterval=100.; oldtime=time.time()
    def mainloop(self):
        if d.paused: time.sleep(.1)
        else:
            status=d.getchannels()
            if status==2:#we updated the switch data
                self.selectchannel()
            
            #print d.xydata[0][0][12], d.xydata[0][1][12] # print the x and y data, respectively, for the 13th sample on fast adc channel 0
            
            if self.savetofile:
                self.outf.write(str(self.nevents)); self.outf.write(",") # start of each line is the event number
                self.outf.write(str(time.time())); self.outf.write(",") # next column is the time in seconds of the current event
                d.xydata[0][1].tofile(self.outf,",",format="%.3f") # save y data (1) from fast adc channel 0
                self.outf.write("\n") # newline
            
            #if len(HaasoscopeLibQt.max10adcchans)>0: print "slow", d.xydataslow[0][0][99], d.xydataslow[0][1][99] # print the x and y data, respectively, for the 100th sample on slow max10 adc channel 0
            
            #if d.dolockin: print d.lockinamp, d.lockinphase # print the lockin info
            
            #if d.fftdrawn: # print some fft info (the freq with the biggest amplitude)
            #    fftxdata = d.fftfreqplot.get_xdata(); fftydata = d.fftfreqplot.get_ydata()
            #    maxfftydata=np.max(fftydata); maxfftfrq=fftxdata[fftydata.argmax()]
            #    print "max amp=",maxfftydata, "at freq=",maxfftfrq, d.fftax.get_xlabel().replace('Freq ','')
            
            if d.db: print time.time()-d.self.oldtime,"done with evt",self.nevents
            self.nevents += 1
            if self.nevents-self.oldnevents >= self.tinterval:
                elapsedtime=time.time()-self.oldtime
                lastrate = round(self.tinterval/elapsedtime,2)
                print self.nevents,"events,",lastrate,"Hz"
                self.oldtime=time.time()
                if lastrate>40: self.tinterval=500.
                else: self.tinterval=100.
                self.oldnevents=self.nevents
            if d.getone and not d.timedout: self.dostartstop()
                        
            #if elapsedtime>1.0:
            #   self.drawtext() #redraws the measurements

try:    
    win = MainWindow()
    win.setWindowTitle('Haasoscope Qt')
    if not d.setup_connections(): sys.exit()
    if not d.init(): sys.exit()
    win.launch()
    win.dostartstop()
except SerialException:
    print "serial com failed!"

#can change some things after initialization
#d.selectedchannel=0
#d.tellswitchgain(d.selectedchannel)
#d.togglesupergainchan(d.selectedchannel)
#d.toggletriggerchan(d.selectedchannel)
#d.togglelogicanalyzer() # run the logic analyzer
#d.sendi2c("21 13 f0") # set extra pins E24 B0,1,2,3 off and B4,5,6,7 on (works for v8 only)

if standalone:
    sys.exit(app.exec_())
else:
    print "Done, but Qt window still active"
