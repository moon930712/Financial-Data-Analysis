import os
import unicodedata

txt_dir = r'C:\Users\Hubnet\antigravity\excel'
print("Files in dir:")
for filename in os.listdir(txt_dir):
    print(repr(filename), unicodedata.normalize('NFC', filename))
