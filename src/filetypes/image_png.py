import tempfile
import os
import string
from grailutil import getenv, which
from Tkinter import *
from formatter import AS_IS
from PIL import Image, ImageTk

if hasattr(os, 'popen'):
    class parse_image_png:
    
        """Parser for image/png files.
    
        """
    
        def __init__(self, viewer, reload=0):
            self.broken = None
            self.tf = self.tfname = None
            self.viewer = viewer
            self.viewer.new_font((AS_IS, AS_IS, AS_IS, 1))
            self.tfname = tempfile.mktemp()
            self.tf = os.popen('cat >' + self.tfname, 'wb')
            self.label = Label(self.viewer.text, text=self.tfname,
                               highlightthickness=0, borderwidth=0)
            self.viewer.add_subwindow(self.label)
    
        def feed(self, data):
            try:
                self.tf.write(data)
            except IOError, (errno, errmsg):
                self.tf.close()
                self.tf = None
                self.broken = 1
                raise IOError, (errno, errmsg)
    
        def close(self):
            if self.tf:
                self.tf.close()
                self.tf = None
                self.raw_image = Image.open(self.tfname)
                self.label.image = ImageTk.PhotoImage(self.raw_image)
                self.label.config(image=self.label.image)
            if self.tfname:
                try:
                    os.unlink(self.tfname)
                except os.error:
                    pass
            if self.broken:
                # TBD: horrid kludge... don't hate me! ;-)
                self.label.image = PhotoImage(file='icons/sadsmiley.gif')
                self.label.config(image=self.label.image)
                self.viewer.text.insert(END, '\nBroken Image!')
