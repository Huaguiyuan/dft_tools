r"""
Test suite for module `inpconf.py`.
"""
import unittest

if __name__ == '__main__':
    suite = unittest.TestLoader().discover('./')
    unittest.TextTestRunner(verbosity=2, buffer=True).run(suite)

