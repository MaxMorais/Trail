"""
A Gopher protocol API

Martin C. Doege
2013-01-29

Code based on Python-2.7.1/Demos/sockets/gopher.py by Guido van Rossum
"""


import string
import sre

import string
import sys
import os
import socket
import tkSimpleDialog

from urllib import unquote, splithost, splitport, splituser, \
     splitpasswd, splitattr, splitvalue, quote
from urlparse import urljoin
from urlparse import urlparse
import mimetools
import textwrap

from Assert import Assert

# wrap text lines longer than:
MAX_TEXT_WIDTH = 80

# Stages
META = 'META'
DATA = 'DATA'
EOF = 'EOF'
DONE = 'DONE'


LISTING_HEADER = """<HTML>
<HEAD><TITLE>Gopher Directory: %(url)s</TITLE></HEAD>
<BODY>
<H1>Gopher Directory: %(url)s</H1>
<PRE>"""

LISTING_TRAILER = """</PRE>
</BODY>
"""

# Default selector, host and port
DEF_SELECTOR = ''
DEF_HOST     = 'gopher.floodgap.com'
DEF_PORT     = 70

# Dictionary mapping types to strings
typename = {'0': '[TEXT]', '1': '[DIR]', '2': '[CSO]', '3': '[ERROR]', \
        '4': '[BINHEX]', '5': '[ZIP]', '6': '[UUENCODE]', '7': '[SEARCH]', \
        '8': '[TELNET]', '9': '[BINARY]', '+': '[REDUNDANT]', 's': '[SOUND]', \
        'g': '[GIF]', 'h': '[HTML]', 'I': '[IMAGE]', 'T': '[TN3270]', \
        'p': '[PNG]', ';': '[MOVIE]', 'd': '[PDF]', '!': '[ERROR]'}

# Oft-used characters and strings
CRLF = '\r\n'
TAB = '\t'

####################################################
# I/O functions
####################################################


# Open a TCP connection to a given host and port
def open_socket(host, port):
    if not port:
        port = DEF_PORT
    elif type(port) == type(''):
        port = string.atoi(port)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(8)
    s.connect((host, port))
    return s

# Send a selector to a given host and port, return a file with the reply
def send_request(selector, host, port):
    s = open_socket(host, port)
    s.send(selector + CRLF)
    s.shutdown(1)
    return s.makefile('r')

# Get a menu in the form of a list of entries
def get_menu(selector, host, port):
    f = send_request(selector, host, port)
    list = []
    while 1:
        line = f.readline()
        if not line:
            print '(Unexpected EOF from server)'
            break
        if line[-2:] == CRLF:
            line = line[:-2]
        elif line[-1:] in CRLF:
            line = line[:-1]
        if line == '.':
            break
        if not line:
            print '(Empty line from server)'
            continue
        typechar = line[0]
        parts = string.splitfields(line[1:], TAB)
        if len(parts) < 4 and typechar not in ('i', '3', '!'):
            print '(Bad line from server: %r)' % (line,)
            continue
        if len(parts) > 4:
            print '(Extra info from server: %r)' % (parts[4:],)
        parts.insert(0, typechar)
        list.append(parts)
    f.close()
    return list

# Get a text file as a list of lines, with trailing CRLF stripped
def get_textfile(selector, host, port):
    list = []
    get_alt_textfile(selector, host, port, list.append)
    return list

# Get a text file and pass each line to a function, with trailing CRLF stripped
def get_alt_textfile(selector, host, port, func):
    f = send_request(selector, host, port)
    while True:
        line = f.readline()
        if not line:
            print '(Unexpected EOF from server)'
            break
        if line[-2:] == CRLF:
            line = line[:-2]
        elif line[-1:] in CRLF:
            line = line[:-1]
        if line == '.':
            break
        if line[:2] == '..':
            line = line[1:]
        # If the text is not valid UTF-8, assume it's in ISO 8859-1
        #   and convert it to UTF-8 for Tkinter:
        try:
            line.decode('utf-8')
        except:
            line = line.decode('latin1').encode('utf-8')
        if len(line) < MAX_TEXT_WIDTH:
            func(line)
        else:
            ll = textwrap.wrap(line, width = MAX_TEXT_WIDTH)
            for x in ll:
                func(x)
    f.close()

# Get a binary file as one solid data block
def get_binary(selector, host, port):
    f = send_request(selector, host, port)
    data = f.read()
    f.close()
    return data

####################################################
# Browsing functions
####################################################

# Browse a menu
def browse_menu(selector, host, port):
    data = ''
    list = get_menu(selector, host, port)
    for i in range(len(list)):
        item = list[i]
        iname = ''
        typechar, description = item[0], item[1]

        if typename.has_key(typechar):
            iname += typename[typechar]
        else:
            if typechar != 'i':
                iname += '(TYPE=' + repr(typechar) + ')'
        iname += description
        bold_line = False
        if typechar in ('2', '7', '8', 'T'):
            bold_line = True
        if typechar not in ('i', 'h', '3', '!'):
            [i_selector, i_host, i_port] = item[2:5]
            url = "gopher://%s:%s/%s%s" % (i_host, i_port, typechar, i_selector)
            url = url.replace(' ', "%20")
            if bold_line:
                data += '<B><A HREF="%s">%s</A></B>' % (url, iname)
            else:
                data += '<A HREF="%s">%s</A>' % (url, iname)
        elif typechar == 'h':
            [i_selector, i_host, i_port] = item[2:5]
            if i_selector[:4] == 'URL:':
                url = i_selector[4:]
                bold_line = True
            elif i_selector[:5] == '/URL:':
                url = i_selector[5:]
                bold_line = True
            else:
                url = "gopher://%s:%s/h%s" % (i_host, i_port, i_selector)
            if bold_line:
                data += '<B><A HREF="%s">%s</A></B>' % (url, iname)
            else:
                data += '<A HREF="%s">%s</A>' % (url, iname)
        else:
            data += iname
        data += '\n'
    return (LISTING_HEADER % {'url': selector}) + data + LISTING_TRAILER

####################################################
# Gopher class
####################################################

class gopher_access:

    def __init__(self, url, method, params):
        try:
            o = urlparse(url)
            if o.port == None:
                port = 70
            else:
                port = o.port
            host = o.hostname
            selector = o.path
            if o.query:
                selector += '?' + o.query
            selector = selector.replace("%20", ' ')
            if not selector or selector == '/' or len(selector) < 3:
                self.ctype = "text/html"
                self.data = browse_menu('', host, port)                
            elif selector[0] == '/':
                if selector[1] == '1':
                    self.ctype = "text/html"
                    self.data = browse_menu(selector[2:], host, port)
                elif selector[1] == '0':
                    self.ctype = "text/plain"
                    self.data = '\n'.join(get_textfile(selector[2:], host, port))
                elif selector[1] == 'h':
                    self.ctype = "text/html"
                    self.data = '\n'.join(get_textfile(selector[2:], host, port))
                elif selector[1] == '7':
                    search_term = tkSimpleDialog.askstring("Search engine", "Query:")
                    self.ctype = "text/html"
                    if search_term:
                        self.data = browse_menu(selector[2:] + TAB + search_term, host, port)
                    else:
                        self.data = "No query supplied."
                elif selector[1] == '2':
                    search_term = tkSimpleDialog.askstring("CSO search", "Query:")
                    if search_term[:6] != "query ":
                        search_term = "query %s return all" % search_term
                    self.ctype = "text/html"
                    if search_term:
                        self.data = browse_menu(selector[2:] + TAB + search_term + "\nquit\n", host, port)
                    else:
                        self.data = "No CSO query supplied."
                elif selector[1] == 'g':
                    self.ctype = "image/gif"
                    self.data = get_binary(selector[2:], host, port)
                elif selector[1] in ('I', 'p'):
                    if selector[-4:].lower() == '.png':
                        self.ctype = "image/png"
                    if selector[-4:].lower() == '.jpg' or selector[-5:].lower() == '.jpeg':
                        self.ctype = "image/jpeg"
                    self.data = get_binary(selector[2:], host, port)
                else:
                    self.ctype = "application/octet-stream"
                    self.data = get_binary(selector[2:], host, port)
            else:
                self.ctype = "text/html"
                self.data = browse_menu(selector, host, port)                
                
        except:
            raise
            #raise IOError, ('gopher error')
        #print self.data
        self.state = META

    def pollmeta(self):
        Assert(self.state == META)
        return "Ready", 1

    def getmeta(self):
        Assert(self.state == META)
        self.state = DATA
        headers = {}
        headers['content-type'] = self.ctype
        headers['content-length'] = "%u" % len(self.data)
        self.lines = []                 # Only used of self.isdir
        return 200, "OK", headers

    def polldata(self):
        Assert(self.state in (EOF, DATA))
        return "Ready", 1

    def getdata(self, maxbytes):
        if self.state == DATA:
            data = self.data
            self.state = EOF
            return data
        return ''

    def escape(self, s):
        if not s: return ""
        s = s.replace('&', '&amp;') # Must be done first
        s = s.replace('<', '&lt;')
        s = s.replace('>', '&gt;')
        return s

    def fileno(self):
        return -1

    def close(self):
        pass

