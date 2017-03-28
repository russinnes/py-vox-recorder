# py-vox-recorder
Python based sound-activated voice recorder (Wx Python)

This is a small GUI to record system audio input. The recording threshold is adjustable via the GUI. A new file is created every hour, but only contains audio which is above the threshold, eliminating deadspace. An adjutable record tail can be set to keep the recording hanging for smoothing / squelching. Only tested on Linux. 
