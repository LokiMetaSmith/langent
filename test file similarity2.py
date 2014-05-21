
import profile
import re
import os
import difflib

import sys
import subprocess
import os
import glob
def compair_downloads():
        path ="C:\Users\Owner\Downloads\*"
        cap = "capture.bin"
        output = []
        a = open(cap,'r')
        d = a.read()
        length_a = len(d)
        for infile in glob.iglob(path):
                
                
                if os.path.isfile(infile):
                        print infile
                        b = open(infile,'r')
                        e = b.read()
                        c = difflib.SequenceMatcher(None, d, e)
                        b.close()
                        length_b = len(e)
                        print c.find_longest_match(0,length_a,0,length_b)
                        
                        #output.append((infile,len(c.get_opcodes())))
                        #print output
                
                        
def compair_radio_raw():
        b = open('C:\\Users\\Owner\\Downloads\\100-S001.pdf','r')
        c = b.read()
        cap = "capture.bin"
        output = []
        a = open(cap,'r')
        d = a.read()

        e = difflib.SequenceMatcher(None, d,b.read() )



        f = e.get_opcodes()
        print len(f)
        print len(f)*5
        additup = 0
        print f

        for q in f:
                print q[4]-q[3]

        for q in f:
                additup += (q[4]-q[3])-5

        print additup
def naive_search():
        b = open('C:\\Users\\Owner\\Downloads\\100-S001.pdf','r')
        c = b.read()
        cap = "capture.bin"
        output = []
        a = open(cap,'r')
        d = a.read()
        length_a = len(d)
        length_b = len(c)
        if length_a > length_b:
                for index_a in range(length_a-length_b):
                        print d[index_a:length_b] and c

##Rabin–Karp algorithm
def Rabin_Karp_Matcher(text, pattern, d, q):
    n = len(text)
    m = len(pattern)
    h = pow(d,m-1)%q
    p = 0
    t = 0
    result = []
    for i in range(m): # preprocessing
        p = (d*p+ord(pattern[i]))%q
        t = (d*t+ord(text[i]))%q
    for s in range(n-m+1): # note the +1
        if p == t: # check character by character
            match = True
            for i in range(m):
                if pattern[i] != text[s+i]:
                    match = False
                    break
            if match:
                result = result + [s]
        if s < n-m:
            t = (t-h*ord(text[s]))%q # remove letter s
            t = (t*d+ord(text[s+m]))%q # add letter s+m
            t = (t+q)%q # make sure that t >= 0
    return result
def find_longest_match_list():
        b = open('C:\\Users\\Owner\\Downloads\\100-S001.pdf','r')
        c = b.read()
        cap = "capture.bin"
        output = []
        a = open(cap,'r')
        d = a.read()
        length_a = len(d)
        length_b = len(c)
        for x in range(length_b):
                print Rabin_Karp_Matcher(d,c,8,int(0x85ebca6b))##e = difflib.SequenceMatcher(None, d,c )
        ##e.find_longest_match(0,length_a,0,length_b)
                
