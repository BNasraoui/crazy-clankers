"""Shared anime head surface, in metres relative to the eye line.

HeadShape is the reusable construction for passengers. Width, height, depth,
jaw_width and nose can vary independently without changing the cylindrical UV
contract. Character hair and facial pigment remain separate art inputs.
"""
from dataclasses import dataclass
import math

# Height, half-width, front depth, rear depth. The lower rings sweep from a
# soft chin through the jaw to the cheek; the upper rings form an egg cranium.
SECTIONS = (
    (-.108,.012,.067,.000),(-.102,.027,.077,.006),(-.086,.043,.080,.020),
    (-.060,.056,.075,.038),(-.038,.069,.073,.059),(-.019,.077,.074,.076),
    (0,.079,.075,.087),(.021,.078,.078,.093),(.042,.077,.079,.095),
    (.064,.072,.074,.092),(.085,.063,.061,.081),(.103,.044,.040,.057),
    (.115,.016,.014,.023),(.117,.002,.002,.003))


@dataclass(frozen=True)
class HeadShape:
    width: float = 1.0
    height: float = 1.0
    depth: float = 1.0
    jaw_width: float = 1.0
    nose: float = 1.0

    @property
    def sections(self):
        return tuple((y*self.height, w*self.width*(1+(self.jaw_width-1)*max(0,min(1,-y/.06))),
                      front*self.depth, rear*self.depth) for y,w,front,rear in SECTIONS)

    def section(self, y):
        sections = self.sections
        i = next((i for i in range(1,len(sections)) if sections[i][0]>=y), len(sections)-1)
        a,b = sections[i-1],sections[i]
        t = max(0,min(1,(y-a[0])/(b[0]-a[0])))
        # Monotone cubic interpolation keeps silhouette tangents continuous and
        # cannot overshoot the chin or crown at closely spaced end sections.
        def slope(j, k):
            if j == 0:
                return (sections[1][k]-sections[0][k])/(sections[1][0]-sections[0][0])
            if j == len(sections)-1:
                return (sections[j][k]-sections[j-1][k])/(sections[j][0]-sections[j-1][0])
            left = (sections[j][k]-sections[j-1][k])/(sections[j][0]-sections[j-1][0])
            right = (sections[j+1][k]-sections[j][k])/(sections[j+1][0]-sections[j][0])
            return 0 if left*right<=0 else 2*left*right/(left+right)
        h = b[0]-a[0]
        return tuple((2*t**3-3*t*t+1)*a[k]+(t**3-2*t*t+t)*h*slope(i-1,k)
                     +(-2*t**3+3*t*t)*b[k]+(t**3-t*t)*h*slope(i,k) for k in range(1,4))

    def surface(self, theta, y):
        rx,front,rear = self.section(y)
        s,c = math.sin(theta),math.cos(theta)
        x = rx*s
        z = front*c if c>=0 else rear*c
        if c>0:
            # Low ridge and rounded tip, integrated into the curved face.
            nx,ny = x/self.width,y/self.height
            z += self.depth*self.nose*(.005*math.exp(-(nx/.012)**2-((ny+.018)/.025)**2)
                                      +.006*math.exp(-(nx/.012)**2-((ny+.034)/.010)**2))
            z += self.depth*.003*math.exp(-(nx/.030)**4-((ny+.061)/.016)**2)
        return x,y,z
