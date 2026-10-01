"""Run in Blender: regression limits for the shared young-adult head surface."""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from techbro_head import surface

checks = {
    'jaw tapers below cheeks': surface(math.pi/2, -.060).x / surface(math.pi/2, -.019).x < .80,
    'cheeks turn away gradually': surface(math.pi/4, 0).z < .060,
    'nose is understated': surface(0, -.037).z - surface(0, .021).z < .018,
}
for name, passed in checks.items():
    print(('PASS' if passed else 'FAIL') + ': ' + name)
assert all(checks.values()), 'Head silhouette regression limits failed'
