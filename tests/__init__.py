import os
import sys

current = os.path.dirname(os.path.abspath(__file__))
root = os.path.normpath(os.path.join(current, '..'))
sys.path = ['..'] + sys.path
