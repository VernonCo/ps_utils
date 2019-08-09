
import os, nose2, sys
sys.path.append(os.path.dirname(os.getcwd()))

if __name__ == "__main__":
    # unittest2.main()
    nose2.discover()
