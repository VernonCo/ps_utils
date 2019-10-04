#!/bin/python3
import sys, inspect

class __LINE__(object):

    def __repr__(self):
        try:
            raise Exception
        except:
            return str(sys.exc_info()[2].tb_frame.f_back.f_lineno)

__LINE__ = __LINE__()

class __FILE__(object):

    def __repr__(self):
        try:
            raise Exception
        except:
            return inspect.currentframe().f_code.co_filename

__FILE__ = __FILE__()
