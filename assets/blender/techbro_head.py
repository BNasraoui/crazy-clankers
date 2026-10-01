"""Tech Bro head: section-modelled facial volume, cylindrical UVs, broad swept hair.

All modelling dimensions are metres in game coordinates. No lighting in textures.
The back seam of the head unwrap is at +/- pi; hair islands run root to tip.
"""
import math
from mathutils import Vector

from head_shape import HeadShape

SHAPE = HeadShape()
SECTIONS = SHAPE.sections
interp = SHAPE.section


def surface(theta, y):
    return Vector(SHAPE.surface(theta, y))


def paint_head(A,palette,shape=SHAPE):
    """Rasterize the committed transparent facial ink onto the cylindrical UV atlas.

    This is inverse UV sampling, not camera projection: both eyes and the smile
    travel around the cheek surface with its seam at the back of the head.
    Only pigment/ink/eye whites are in the source, never skin or lighting.
    """
    import numpy as np
    from pathlib import Path
    decal=A.Image.open(Path(__file__).parent/'textures/techbro-face-decal.png').convert('RGBA')
    source=np.asarray(decal,dtype=np.float32)/255
    # Remove neutral tonal variation in the generated whites; keep alpha and ink.
    rgb=source[:,:,:3]
    white=(rgb.min(axis=2)>.58)&((rgb.max(axis=2)-rgb.min(axis=2))<.10)
    rgb[white]=np.array((255,252,243))/255
    # Brows are flat brown pigment; no gradient from the generated drawing.
    rgb[:505]=np.array(A.rgb(0x352A24))/255
    size=2048
    u=(np.arange(size)+.5)/size
    v=1-(np.arange(size)+.5)/size
    y=(v*.240-.115)*shape.height
    rx=np.array([shape.section(float(height))[0] for height in y])
    theta=(u-.5)*2*math.pi
    x=rx[:,None]*np.sin(theta)[None,:]
    sx=x/(.000145*shape.width)+650
    sy=np.broadcast_to((570-y/(.000160*shape.height))[:,None],sx.shape)
    inside=(sx>=0)&(sx<decal.width-1)&(sy>=0)&(sy<decal.height-1)&(np.cos(theta)[None,:]>0)
    sx=np.clip(sx,0,decal.width-2);sy=np.clip(sy,0,decal.height-2)
    ix=sx.astype(int);iy=sy.astype(int);fx=(sx-ix)[...,None];fy=(sy-iy)[...,None]
    sample=(source[iy,ix]*(1-fx)+source[iy,ix+1]*fx)*(1-fy)+(source[iy+1,ix]*(1-fx)+source[iy+1,ix+1]*fx)*fy
    alpha=sample[:,:,3:4]*inside[:,:,None]
    skin=np.array(A.rgb(palette['face']))/255
    out=sample[:,:,:3]*alpha+skin*(1-alpha)
    A.TEX_DIR.mkdir(parents=True,exist_ok=True)
    path=A.TEX_DIR/'techbro_face_cylindrical.png'
    A.Image.fromarray((out*255+.5).astype(np.uint8)).save(path)
    return path


def paint_hair(A,palette):
    pt=A.Painter(1024,A.rgb(palette['hair']),.5,0,ss=2)
    # Deliberate sparse pen marks, not prepainted lighting or dozens of strands.
    for k,x in enumerate([-.34,-.14,.17,.35]):
        pt.stroke([(x*.7,.96),(x,.78),(x*.95,.50),(x*.65,.25),(x*.18,.06)],
                  [.000,.004,.006,.004,0],(42,32,28))
    return pt.save('techbro_hair_flow')


LOCKS = [
  # main sweep over exposed forehead, from left part towards cup side
  ([(-.041,.096,.059),(-.014,.129,.066),(.022,.133,.071),(.058,.105,.083),(.080,.073,.075),(.089,.050,.061)], .029,.013),
  ([(-.046,.099,.039),(-.019,.129,.029),(.031,.132,.032),(.075,.112,.033),(.096,.090,.026),(.094,.063,.010)],.037,.018),
  ([(-.043,.091,.035),(-.058,.111,.045),(-.085,.097,.052),(-.095,.069,.040),(-.096,.047,.022)],.026,.011),
  # forehead curl on the other side of the part
  ([(-.040,.106,.068),(-.012,.114,.088),(.018,.091,.105),(.025,.058,.101),(.037,.034,.085)],.025,.008),
  # Layered diagonal forehead sweep.
  ([(-.052,.105,.050),(-.024,.106,.079),(.006,.079,.111),(.010,.048,.102),(.022,.031,.079)],.016,.006),
  # right temple flow behind ear, two large waves
  ([(.056,.106,.019),(.100,.094,.008),(.106,.061,-.010),(.100,.031,-.022),(.091,.002,-.026)],.032,.014),
  ([(.040,.124,-.047),(.079,.101,-.062),(.098,.066,-.067),(.092,.026,-.064),(.086,-.015,-.039)],.034,.014),
  # left temple, swept back
  ([(-.060,.089,.016),(-.090,.078,.008),(-.102,.051,-.003),(-.096,.023,-.020),(-.081,.003,-.018)],.029,.014),
  ([(-.036,.126,-.043),(-.080,.108,-.054),(-.101,.067,-.060),(-.096,.025,-.059),(-.082,-.013,-.034)],.036,.014),
  # broad back waves
  ([(.008,.132,-.048),(.034,.111,-.091),(.044,.069,-.112),(.040,.008,-.100),(.024,-.040,-.074)],.034,.012),
  ([(-.018,.129,-.054),(-.045,.103,-.092),(-.051,.061,-.111),(-.049,.004,-.099),(-.030,-.038,-.072)],.032,.011),
  # a single restrained lifted wave on crown
  ([(-.010,.114,-.010),(.014,.148,-.013),(.040,.141,-.026),(.063,.129,-.042),(.065,.125,-.056)],.023,.010),
]
LOCKS += [
  ([(-.035,.103,.020),(-.046,.131,.013),(-.025,.133,.004),(-.014,.126,.010)],.012,.008),
  ([(.012,.113,.005),(.040,.137,.007),(.060,.133,.003),(.072,.122,.006)],.014,.008),
  ([(.065,.087,-.032),(.087,.065,-.046),(.101,.049,-.035),(.109,.057,-.025)],.013,.007),
  ([(-.059,.075,-.035),(-.088,.052,-.039),(-.100,.038,-.029),(-.109,.044,-.015)],.012,.006),
]

# Character-specific hair art, transformed once into eye-relative metres.
LOCKS = [([(x*.88, y*.83+.006*max(0,min(1,(y-.10)/.05))**2*
            (3-2*max(0,min(1,(y-.10)/.05))), z*(.84 if z>0 else .82))
           for x,y,z in points], width, depth) for points,width,depth in LOCKS]


def build_head_mesh(A,C,mats,materials,root,centre,neck,tilt_spec):
    from anime_head import build_head_mesh as build_shared_head
    return build_shared_head(A,C,mats,materials,root,centre,neck,tilt_spec,SHAPE,LOCKS)
