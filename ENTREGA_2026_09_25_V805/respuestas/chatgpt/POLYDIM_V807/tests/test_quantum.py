import sys,pathlib,unittest,math
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'python'))
from polydim.quantum import synthesize_grid
class Quantum(unittest.TestCase):
 def test_three_axes(self):
  for axis in ('x','y','z'):
   for k in range(-8,9):self.assertLess(synthesize_grid(k*math.pi/4,axis)[1],1e-12)
 def test_off_grid(self):
  with self.assertRaises(NotImplementedError):synthesize_grid(.123)
if __name__=='__main__':unittest.main(verbosity=2)
