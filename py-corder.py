#!/usr/bin/python
## Default path for storing recordings
RECORD_PATH = '~/'

# Amount of time to continue recording after input drops below threshold (smoothing)
HANGDELAY = 3
# Recording trigger default threshold on startup
THRESHOLD = 3

import wx
import random
import audioop
import pyaudio
import threading
import time
import numpy as np
import Queue
import wave
import wx.lib.agw.peakmeter as PM



RUNNING = 1
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 12000
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,channels=CHANNELS,rate=RATE,input=True,frames_per_buffer=CHUNK)

RMSDATA = {}
RMSDATA['CURRENT'] = 0
RMSDATA['DATA'] = []
RMSDATA['TRIGGERSTART'] = None
RMSDATA['TRIGGEREND'] = None
RMSDATA['TRIGGERVAL'] = 10 #default
RMSDATA['RECORD_CLOCK'] = '' #default
RMSDATA['RECORDFLAG'] = False
RMSDATA['_RECORDFLAG'] = False

class _streamProcessor(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.queue = queue
        
    def run(self):
        while RUNNING:
            if RMSDATA['RECORD_CLOCK'] != time.strftime("%Y%m%d-%H"):
                self.filename = RECORD_PATH+time.strftime("%Y%m%d-%H%M%S.wav")
                data = self.queue.get(1)
                self.wf = wave.open(self.filename, 'wb')
                self.wf.setnchannels(CHANNELS)
                self.wf.setsampwidth(p.get_sample_size(FORMAT))
                self.wf.setframerate(RATE)
                RMSDATA['RECORD_CLOCK'] = time.strftime("%Y%m%d-%H")
            while RMSDATA['RECORD_CLOCK'] == time.strftime("%Y%m%d-%H"):
                while RMSDATA['RECORDFLAG']:
                    if self.queue.qsize() > 0:
                        self.wf.writeframes(self.queue.get(1))
                    else: time.sleep(0.2)
                data = self.queue.get(1) # throw it away... wait for record flag
                time.sleep(0.1)
            if self.wf:
                self.close()
            time.sleep(0.1)

    def close(self):
        if self.wf:
            self.wf.close()



class _recordTimer(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.timer = 0
        
    def run(self):
        while RUNNING:
            if time.time() - self.timer < HANGDELAY: RMSDATA['RECORDFLAG'] = True
            if time.time() - self.timer > HANGDELAY + 1: RMSDATA['RECORDFLAG'] = False
            time.sleep(0.1)
                
    def reset_timer(self, timer):
        self.timer = timer

class _streamReader(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.queue = queue
        
    def run(self):
        while RUNNING:
            data = stream.read(CHUNK, exception_on_overflow = False)
            self.queue.put(data)
            data2 = np.fromstring(data,dtype=np.int16)
            peak=(np.average(np.abs(data2)))/64
            if len(RMSDATA['DATA']) < 1:
                RMSDATA['DATA'].append(int(peak))
            if len(RMSDATA['DATA']) == 1:
                RMSDATA['DATA'] = RMSDATA['DATA'][1:]
                RMSDATA['DATA'].append(int(peak))
            RMSDATA['CURRENT'] = int(peak)
            time.sleep(0.1)


class MyFrame(wx.Frame):

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, "Vox Audio Recorder", size=(500, 200))
        panel = wx.Panel(self)
        # default rx trigger value
        self.trigger = THRESHOLD
        self.recording = 0 
        # Initialize Objects
        self.vertPeak = PM.PeakMeterCtrl(panel, -1, size=(450,15), pos=(25, 130), style=wx.SIMPLE_BORDER, agwStyle=PM.PM_HORIZONTAL)
        self.vertPeak.SetMeterBands(1, 100)
        self.slider = wx.Slider(panel, value = self.trigger, minValue = 1, maxValue = 100,pos=(25, 100),size=(450,20),style = wx.SL_HORIZONTAL)
        self.slider.Bind(wx.EVT_SLIDER, self.OnSliderScroll) 
        closeBtn = wx.Button(panel, label="Close", pos=(200, 5), size=(80, 25))
        closeBtn.Bind(wx.EVT_BUTTON, self.onClose)
        lbl = wx.StaticText(panel,-1,pos=(393,80))
        lbl.SetLabel('Recording')
        thresh = wx.StaticText(panel,-1,pos=(30,80))
        thresh.SetLabel('Trigger Level')
        font1 = wx.Font(20, wx.MODERN, wx.NORMAL, wx.NORMAL, False, u'Consolas')
        self.filedescriptor = wx.StaticText(panel, -1, "Current File", pos=(145, 50) )
        self.filedescriptor.SetFont(font1)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.filetimer = wx.Timer(self)
        self.filetimer.Start(1000)
        wx.CallLater(500, self.Start)

    def onClose(self, event):
        global RUNNING
        RUNNING = 0
        time.sleep(2)
        PROCESSOR.close()
        self.Close()

    def Start(self):
        self.timer.Start(1000/4)            # 5 fps
        self.vertPeak.Start(1000/5)        # 18 fps
        self.FileIndicator()

    def OnTimer(self, event):
        try:
            self.vertPeak.SetData(RMSDATA['DATA'], 0, len(RMSDATA['DATA']))
            self.currentLevel = RMSDATA['DATA'][0]
            if self.currentLevel > self.trigger:
                RT.reset_timer(time.time())
            self.Updater()
        except AssertionError:
            pass

    def OnSliderScroll(self, e): 
        self.trigger = self.slider.GetValue()
    
    def Updater(self):
        if RMSDATA['RECORDFLAG'] != RMSDATA['_RECORDFLAG']:
            self.RecordIndicator(RMSDATA['RECORDFLAG'])
            RMSDATA['_RECORDFLAG'] = RMSDATA['RECORDFLAG']
            
    def RecordIndicator(self, flag):
        flags={ 0:'red',1:'green'}
        dc = wx.PaintDC(self)
        dc.SetPen(wx.Pen("black"))
        dc.SetBrush(wx.Brush("%s" % flags[flag])) #set brush transparent for non-filled rectangle
        dc.DrawRectangle(460,85,10,10)
        
    def FileIndicator(self):
        self.filedescriptor.SetLabel(PROCESSOR.filename)
        wx.CallLater(1000, self.FileIndicator)



sample_queue = Queue.Queue()
app = wx.PySimpleApp()
frame = MyFrame(None)
app.SetTopWindow(frame)
frame.Show()
STREAMER=_streamReader(sample_queue)
STREAMER.start()
PROCESSOR=_streamProcessor(sample_queue)
PROCESSOR.start()
RT = _recordTimer()
RT.start()
app.MainLoop()
